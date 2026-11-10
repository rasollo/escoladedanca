from django import forms

from .models import Aluno


class AlunoForm(forms.ModelForm):
    """RF01 — dados obrigatórios: apenas o nome (fluxo 01)."""

    class Meta:
        model = Aluno
        fields = ["nome", "telefone", "email", "data_nascimento", "observacoes", "ativo"]
        widgets = {
            "data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_nome(self):
        nome = " ".join(self.cleaned_data["nome"].split())
        if len(nome) < 3:
            raise forms.ValidationError("Informe o nome completo do aluno.")
        return nome
