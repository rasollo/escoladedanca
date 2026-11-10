from datetime import date

from django import forms
from django.utils import timezone

from alunos.models import Aluno
from professores.models import Professor

from .models import Movimentacao

DATE = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")


def um_mes_depois(d: date) -> date:
    ano, mes = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for dia in (d.day, 30, 29, 28):
        try:
            return date(ano, mes, dia)
        except ValueError:
            continue


class _MovimentacaoForm(forms.ModelForm):
    tipo_fixo = None
    valores_fixos: dict = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O tipo é definido antes da validação para que Movimentacao.clean()
        # aplique as regras de entrada/saída (RN01).
        self.instance.tipo = self.tipo_fixo
        for campo, valor in self.valores_fixos.items():
            setattr(self.instance, campo, valor)
        if not self.instance.pk and "data_pagamento" in self.fields:
            self.fields["data_pagamento"].initial = timezone.localdate()
        if "aluno" in self.fields:
            self.fields["aluno"].queryset = Aluno.objects.filter(ativo=True)
        if "professor" in self.fields:
            self.fields["professor"].queryset = Professor.objects.filter(ativo=True)


class EntradaForm(_MovimentacaoForm):
    """RF06 / RF08 / RF10 — fluxo 08."""

    tipo_fixo = Movimentacao.Tipo.ENTRADA

    class Meta:
        model = Movimentacao
        fields = ["valor", "data_pagamento", "origem", "forma_pagamento", "aluno",
                  "validade", "descricao"]
        widgets = {"data_pagamento": DATE, "validade": DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["origem"].required = True
        self.fields["forma_pagamento"].required = True
        self.fields["aluno"].help_text = "Obrigatório quando a origem é mensalidade."


class MensalidadeForm(_MovimentacaoForm):
    """RF11 / RN06 — fluxo 10. A mensalidade é sempre uma entrada."""

    tipo_fixo = Movimentacao.Tipo.ENTRADA
    valores_fixos = {"origem": Movimentacao.Origem.MENSALIDADE}

    class Meta:
        model = Movimentacao
        fields = ["aluno", "valor", "data_pagamento", "forma_pagamento", "validade",
                  "descricao"]
        widgets = {"data_pagamento": DATE, "validade": DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["aluno"].required = True
        self.fields["forma_pagamento"].required = True
        if not self.instance.pk:
            self.fields["validade"].initial = um_mes_depois(timezone.localdate())


class SaidaForm(_MovimentacaoForm):
    """RF07 / RF09 / RF10 / RF12 — fluxo 09."""

    tipo_fixo = Movimentacao.Tipo.SAIDA

    class Meta:
        model = Movimentacao
        fields = ["valor", "data_pagamento", "categoria", "professor", "referencia",
                  "forma_pagamento", "validade", "descricao"]
        widgets = {"data_pagamento": DATE, "validade": DATE, "referencia": DATE}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].required = True
        self.fields["professor"].help_text = "Obrigatório quando a categoria é salário."


class CalculoSalarioForm(forms.Form):
    """RF13 — escolha do professor e do mês para o cálculo."""

    professor = forms.ModelChoiceField(queryset=Professor.objects.filter(ativo=True))
    mes = forms.CharField(
        label="Mês", widget=forms.DateInput(attrs={"type": "month"}),
    )

    def clean_mes(self):
        valor = self.cleaned_data["mes"]
        try:
            ano, mes = (int(p) for p in valor.split("-"))
            return date(ano, mes, 1)
        except ValueError:
            raise forms.ValidationError("Informe o mês no formato AAAA-MM.")


class FiltroMovimentacoesForm(forms.Form):
    inicio = forms.DateField(label="De", required=False, widget=DATE)
    fim = forms.DateField(label="Até", required=False, widget=DATE)
    tipo = forms.ChoiceField(
        required=False, choices=[("", "Entradas e saídas")] + list(Movimentacao.Tipo.choices)
    )
    q = forms.CharField(label="Buscar", required=False)

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["inicio"] > dados["fim"]:
            raise forms.ValidationError("A data inicial deve ser anterior à final.")
        return dados
