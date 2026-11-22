from django import forms

from escoladedanca.utils import DataBR, validar_nascimento

from .models import Aluno


class AlunoForm(forms.ModelForm):
    """RF01 — dados obrigatórios: apenas o nome (fluxo 01)."""

    class Meta:
        model = Aluno
        fields = ["nome", "telefone", "email", "data_nascimento", "observacoes", "ativo"]
        widgets = {
            "data_nascimento": DataBR(),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {"data_nascimento": "Opcional. Aparece em Aniversariantes (somente dia e mês)."}

    def clean_data_nascimento(self):
        return validar_nascimento(self.cleaned_data.get("data_nascimento"))

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if len(nome) < 3:
            raise forms.ValidationError("Informe o nome completo do aluno.")
        return nome
