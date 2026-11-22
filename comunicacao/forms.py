from django import forms

from aulas.models import Turma

from .models import Comunicado, Solicitacao


class ComunicadoForm(forms.ModelForm):
    class Meta:
        model = Comunicado
        fields = ["turma", "titulo", "mensagem"]
        widgets = {"mensagem": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, turmas, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["turma"].queryset = turmas
        self.fields["turma"].label = "Aula"


class SolicitacaoForm(forms.ModelForm):
    class Meta:
        model = Solicitacao
        fields = ["tipo", "mensagem"]
        widgets = {"mensagem": forms.Textarea(attrs={"rows": 5})}
        help_texts = {"mensagem": "Explique o que precisa. A administração responde por aqui."}


class RespostaForm(forms.ModelForm):
    class Meta:
        model = Solicitacao
        fields = ["status", "resposta"]
        widgets = {"resposta": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        dados = super().clean()
        if dados.get("status") in (Solicitacao.Status.CONCLUIDA, Solicitacao.Status.RECUSADA) \
                and not (dados.get("resposta") or "").strip():
            self.add_error("resposta", "Explique ao aluno a conclusão ou a recusa.")
        return dados


def turmas_que_pode_comunicar(papel, user):
    from escoladedanca.rbac import ADMINISTRATIVO
    qs = Turma.objects.filter(ativa=True).select_related("modalidade", "sala")
    if papel == ADMINISTRATIVO:
        return qs
    return qs.filter(professor__usuario=user)
