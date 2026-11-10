from django import forms

from .models import Professor


class ProfessorForm(forms.ModelForm):
    """RF17 — fluxo 02."""

    class Meta:
        model = Professor
        fields = ["nome", "telefone", "email", "valor_por_aluno", "ativo"]

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if len(nome) < 3:
            raise forms.ValidationError("Informe o nome completo do professor.")
        return nome
