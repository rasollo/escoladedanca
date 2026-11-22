from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.db import transaction

from alunos.models import Aluno
from escoladedanca.rbac import (ADMINISTRATIVO, ALUNO, PAPEIS, PROFESSOR, adicionar_papel,
                                atribuir_papel, papeis_do)

from .models import marcar_troca_de_senha
from professores.models import Professor


class NovoUsuarioForm(UserCreationForm):
    """RF25 — o Administrativo cria o acesso e define o papel do usuário.

    Professores e alunos precisam estar vinculados ao próprio cadastro, para
    que vejam apenas as suas aulas, presenças e mensalidades. A senha passa
    pelos validadores do Django e é guardada com hash (RNF03).
    """

    papel = forms.ChoiceField(choices=[(p, p) for p in PAPEIS], initial=PROFESSOR)
    professor = forms.ModelChoiceField(
        queryset=Professor.objects.none(), required=False,
        help_text="Obrigatório para o papel Professor.",
    )
    aluno = forms.ModelChoiceField(
        queryset=Aluno.objects.none(), required=False,
        help_text="Obrigatório para o papel Aluno.",
    )

    exigir_troca = forms.BooleanField(
        label="Exigir troca de senha no primeiro acesso", required=False, initial=True,
        help_text="Recomendado: a senha definida aqui vale só para o primeiro login.")

    class Meta(UserCreationForm.Meta):
        fields = ["papel", "professor", "aluno", "username", "first_name", "email"]
        labels = {"first_name": "Nome", "email": "E-mail"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Só aparecem cadastros que ainda não têm acesso.
        self.fields["professor"].queryset = Professor.objects.filter(
            ativo=True, usuario__isnull=True)
        self.fields["aluno"].queryset = Aluno.objects.filter(ativo=True, usuario__isnull=True)

    def clean(self):
        dados = super().clean()
        papel = dados.get("papel")
        if papel == PROFESSOR and not dados.get("professor"):
            self.add_error("professor", "Escolha o professor que vai usar este acesso.")
        if papel == ALUNO and not dados.get("aluno"):
            self.add_error("aluno", "Escolha o aluno que vai usar este acesso.")
        if papel == ADMINISTRATIVO and (dados.get("professor") or dados.get("aluno")):
            raise ValidationError("Usuários administrativos não são vinculados a professor ou aluno.")
        return dados

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=True)
        papel = self.cleaned_data["papel"]
        atribuir_papel(user, papel)
        marcar_troca_de_senha(user, self.cleaned_data.get("exigir_troca", False))
        vinculo = {PROFESSOR: "professor", ALUNO: "aluno"}.get(papel)
        if vinculo:
            cadastro = self.cleaned_data[vinculo]
            cadastro.usuario = user
            cadastro.save(update_fields=["usuario"])
        return user


class PapelExtraForm(forms.Form):
    """Acrescenta um papel a uma conta existente (ex.: professor que também é aluno)."""

    papel = forms.ChoiceField(choices=[(p, p) for p in PAPEIS])
    professor = forms.ModelChoiceField(queryset=Professor.objects.none(), required=False)
    aluno = forms.ModelChoiceField(queryset=Aluno.objects.none(), required=False)

    def __init__(self, *args, usuario, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        atuais = papeis_do(usuario)
        self.fields["papel"].choices = [(p, p) for p in PAPEIS if p not in atuais]
        self.fields["professor"].queryset = Professor.objects.filter(ativo=True, usuario__isnull=True)
        self.fields["aluno"].queryset = Aluno.objects.filter(ativo=True, usuario__isnull=True)

    def clean(self):
        dados = super().clean()
        papel = dados.get("papel")
        if papel == PROFESSOR and not dados.get("professor") and not hasattr(self.usuario, "professor"):
            self.add_error("professor", "Escolha o cadastro de professor desta conta.")
        if papel == ALUNO and not dados.get("aluno") and not hasattr(self.usuario, "aluno"):
            self.add_error("aluno", "Escolha o cadastro de aluno desta conta.")
        return dados

    @transaction.atomic
    def save(self):
        papel = self.cleaned_data["papel"]
        adicionar_papel(self.usuario, papel)
        vinculo = {PROFESSOR: "professor", ALUNO: "aluno"}.get(papel)
        if vinculo and self.cleaned_data.get(vinculo):
            cadastro = self.cleaned_data[vinculo]
            cadastro.usuario = self.usuario
            cadastro.save(update_fields=["usuario"])
        return papel
