from django import forms

from escoladedanca.utils import DataBR, validar_nascimento

from .models import Professor


class ProfessorForm(forms.ModelForm):
    """RF17 — fluxo 02."""

    class Meta:
        model = Professor
        fields = ["nome", "telefone", "email", "data_nascimento", "valor_por_aluno", "ativo"]
        widgets = {"data_nascimento": DataBR()}
        help_texts = {"data_nascimento": "Opcional. Aparece em Aniversariantes (somente dia e mês)."}

    def clean_data_nascimento(self):
        return validar_nascimento(self.cleaned_data.get("data_nascimento"))

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if len(nome) < 3:
            raise forms.ValidationError("Informe o nome completo do professor.")
        return nome
