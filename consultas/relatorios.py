"""Relatórios do período com exportação CSV (somente Administrativo)."""
import csv

from django import forms
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from alunos.models import Aluno
from aulas.models import Chamada, Matricula, Presenca
from escoladedanca.utils import DataBR
from financeiro.models import Cobranca, Movimentacao
from financeiro.services import resumir_cobrancas


class PeriodoForm(forms.Form):
    inicio = forms.DateField(label="De", widget=DataBR())
    fim = forms.DateField(label="Até", widget=DataBR())

    def clean(self):
        dados = super().clean()
        if dados.get("inicio") and dados.get("fim") and dados["inicio"] > dados["fim"]:
            raise forms.ValidationError("A data inicial deve ser anterior à final.")
        return dados


def celula_segura(valor) -> str:
    """Evita injeção de fórmulas ao abrir o CSV em planilhas (=, +, -, @)."""
    texto = "" if valor is None else str(valor)
    if texto[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + texto
    return texto


def _csv(nome, cabecalho, linhas):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{nome}"'
    resp.write("﻿")  # BOM: acentos corretos no Excel
    escritor = csv.writer(resp, delimiter=";")
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow([celula_segura(c) for c in linha])
    return resp


def _br(valor):
    return f"{valor:.2f}".replace(".", ",")


def relatorios(request):
    hoje = timezone.localdate()
    form = PeriodoForm(request.GET or None,
                       initial={"inicio": hoje.replace(day=1), "fim": hoje})
    if form.is_bound and form.is_valid():
        inicio, fim = form.cleaned_data["inicio"], form.cleaned_data["fim"]
    else:
        inicio, fim = hoje.replace(day=1), hoje
    sufixo = f"{inicio:%Y%m%d}-{fim:%Y%m%d}"
    presencas = (Presenca.objects.filter(data__range=(inicio, fim))
                 .select_related("aluno", "turma__modalidade", "turma__professor"))
    cobrancas = (Cobranca.objects.filter(vencimento__range=(inicio, fim)).com_totais()
                 .select_related("aluno", "matricula__turma__modalidade"))
    movs = (Movimentacao.objects.filter(data_pagamento__range=(inicio, fim))
            .select_related("aluno", "professor"))

    exportar = request.GET.get("exportar")
    if exportar == "presencas":
        return _csv(f"presencas_{sufixo}.csv",
                    ["Data", "Aula", "Professor", "Aluno", "Situação"],
                    ([f"{p.data:%d/%m/%Y}", p.turma.nome or p.turma.modalidade, p.turma.professor,
                      p.aluno.nome, "Presente" if p.presente else "Falta"]
                     for p in presencas.order_by("data", "turma_id", "aluno__nome")))
    if exportar == "cobrancas":
        return _csv(f"cobrancas_{sufixo}.csv",
                    ["Competência", "Vencimento", "Aluno", "Aula", "Valor", "Recebido", "Saldo", "Situação"],
                    ([f"{c.competencia:%m/%Y}", f"{c.vencimento:%d/%m/%Y}", c.aluno.nome,
                      c.matricula.turma.nome or c.matricula.turma.modalidade, _br(c.valor),
                      _br(c.recebido), _br(c.saldo), c.get_situacao_display()]
                     for c in cobrancas.order_by("vencimento", "aluno__nome")))
    if exportar == "movimentacoes":
        return _csv(f"movimentacoes_{sufixo}.csv",
                    ["Data", "Tipo", "Classificação", "Forma", "Valor", "Aluno/Professor", "Descrição"],
                    ([f"{m.data_pagamento:%d/%m/%Y}", m.get_tipo_display(), m.classificacao,
                      m.get_forma_pagamento_display(), _br(m.valor), m.aluno or m.professor or "",
                      m.descricao] for m in movs.order_by("data_pagamento", "pk")))

    total_reg = presencas.count()
    presentes = presencas.filter(presente=True).count()
    entradas = movs.filter(tipo="entrada").aggregate(t=Sum("valor"))["t"] or 0
    saidas = movs.filter(tipo="saida").aggregate(t=Sum("valor"))["t"] or 0
    chamadas = Chamada.objects.filter(data__range=(inicio, fim))
    lista_cobrancas = list(cobrancas)
    situacoes = {s: 0 for s in Cobranca.Situacao.values}
    for c in lista_cobrancas:
        situacoes[c.situacao(hoje)] += 1
    mensalidades_recebidas = (movs.filter(tipo="entrada", origem="mensalidade")
                              .aggregate(t=Sum("valor"))["t"] or 0)
    return render(request, "consultas/relatorios.html", {
        "form": form, "inicio": inicio, "fim": fim,
        "alunos_ativos": Aluno.objects.filter(ativo=True).count(),
        "matriculas_ativas": Matricula.objects.filter(data_fim__isnull=True).count(),
        "suspensas": Matricula.objects.filter(data_fim__range=(inicio, fim), situacao="suspensa").count(),
        "canceladas": Matricula.objects.filter(data_fim__range=(inicio, fim), situacao="cancelada").count(),
        "registros": total_reg, "presentes": presentes,
        "frequencia": round(100 * presentes / total_reg) if total_reg else None,
        "chamadas_concluidas": chamadas.filter(situacao="concluida").count(),
        "aulas_canceladas": chamadas.filter(situacao="cancelada").count(),
        "entradas": entradas, "saidas": saidas, "resultado": entradas - saidas,
        "cobrancas": resumir_cobrancas(lista_cobrancas, hoje),
        "situacoes": situacoes,
        "mensalidades_recebidas": mensalidades_recebidas,
        "query": f"inicio={inicio:%d/%m/%Y}&fim={fim:%d/%m/%Y}",
    })
