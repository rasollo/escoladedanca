from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from escoladedanca.utils import redirecionar

from .forms import (CalculoSalarioForm, EntradaForm, FiltroMovimentacoesForm,
                    MensalidadeForm, SaidaForm)
from .models import Movimentacao
from .services import (balanco_mensal, calcular_salario, calcular_saldo,
                       filtrar_movimentacoes)

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def _paginar(request, qs, por_pagina=25):
    return Paginator(qs, por_pagina).get_page(request.GET.get("page"))


def painel(request):
    """Visão geral do módulo financeiro."""
    hoje = timezone.localdate()
    return render(request, "financeiro/painel.html", {
        "saldo": calcular_saldo(),
        "balanco": balanco_mensal(hoje.year, hoje.month),
        "mes_nome": MESES[hoje.month - 1],
        "ultimas": Movimentacao.objects.select_related("aluno", "professor")[:8],
    })


def movimentacoes(request):
    """RF14 — consulta das movimentações (fluxo 12, ramo Movimentações)."""
    form = FiltroMovimentacoesForm(request.GET or None)
    qs = Movimentacao.objects.select_related("aluno", "professor")
    if form.is_valid():
        qs = filtrar_movimentacoes(qs, **form.cleaned_data)
    return render(request, "financeiro/movimentacoes.html", {
        "form": form,
        "pagina": _paginar(request, qs),
        "total": qs.count(),
    })


def saldo(request):
    """RF15 — consulta do saldo (fluxo 12, ramo Saldo)."""
    return render(request, "financeiro/saldo.html", {"saldo": calcular_saldo()})


def balanco(request):
    """RF16 — balanço mensal (fluxo 13)."""
    hoje = timezone.localdate()
    try:
        ano, mes = (int(p) for p in request.GET.get("mes", "").split("-"))
        date(ano, mes, 1)
    except ValueError:
        ano, mes = hoje.year, hoje.month
    return render(request, "financeiro/balanco.html", {
        "balanco": balanco_mensal(ano, mes),
        "mes_valor": f"{ano:04d}-{mes:02d}",
        "mes_nome": f"{MESES[mes - 1]} de {ano}",
    })


def _salvar_movimentacao(request, form_class, titulo, instance=None, initial=None,
                         sucesso=None, voltar=None):
    form = form_class(request.POST or None, instance=instance, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, sucesso or "Movimentação salva.")
        return redirecionar(request, voltar or reverse("financeiro:movimentacoes"))
    return render(request, "form.html", {
        "form": form, "titulo": titulo, "secao": "Financeiro",
        "voltar": voltar or reverse("financeiro:movimentacoes"),
        "next": request.GET.get("next", ""),
    })


def nova_entrada(request):
    """RF06 / RF08 / RF10 — fluxo 08."""
    return _salvar_movimentacao(request, EntradaForm, "Registrar entrada",
                                sucesso="Entrada registrada.")


def nova_saida(request):
    """RF07 / RF09 / RF10 — fluxo 09."""
    return _salvar_movimentacao(request, SaidaForm, "Registrar saída",
                                sucesso="Saída registrada.")


def editar(request, pk):
    mov = get_object_or_404(Movimentacao, pk=pk)
    if mov.tipo == Movimentacao.Tipo.SAIDA:
        form_class = SaidaForm
    elif mov.origem == Movimentacao.Origem.MENSALIDADE:
        form_class = MensalidadeForm
    else:
        form_class = EntradaForm
    return _salvar_movimentacao(request, form_class, "Editar movimentação", instance=mov,
                                sucesso="Movimentação atualizada.")


def excluir(request, pk):
    mov = get_object_or_404(Movimentacao, pk=pk)
    if request.method == "POST":
        mov.delete()
        messages.success(request, "Movimentação excluída.")
        return redirect("financeiro:movimentacoes")
    return render(request, "confirmar_exclusao.html", {
        "objeto": mov, "voltar": reverse("financeiro:movimentacoes"),
    })


def mensalidades(request):
    """RF11 — consulta das mensalidades (fluxo 10)."""
    qs = Movimentacao.objects.filter(origem=Movimentacao.Origem.MENSALIDADE).select_related("aluno")
    aluno_id = request.GET.get("aluno")
    if aluno_id and aluno_id.isdigit():
        qs = qs.filter(aluno_id=aluno_id)
    return render(request, "financeiro/mensalidades.html", {
        "pagina": _paginar(request, qs), "total": qs.count(), "aluno_id": aluno_id,
    })


def nova_mensalidade(request):
    """RF11 / RN06 — registra a mensalidade como entrada financeira (fluxo 10)."""
    initial = {}
    if request.GET.get("aluno", "").isdigit():
        initial["aluno"] = request.GET["aluno"]
    return _salvar_movimentacao(request, MensalidadeForm, "Registrar mensalidade",
                                initial=initial, sucesso="Mensalidade registrada.",
                                voltar=reverse("financeiro:mensalidades"))


def despesas(request):
    """RF12 — consulta das despesas (saídas)."""
    qs = Movimentacao.objects.filter(tipo=Movimentacao.Tipo.SAIDA).select_related("professor")
    categoria = request.GET.get("categoria")
    if categoria in Movimentacao.Categoria.values:
        qs = qs.filter(categoria=categoria)
    return render(request, "financeiro/despesas.html", {
        "pagina": _paginar(request, qs), "total": qs.count(),
        "categorias": Movimentacao.Categoria.choices, "categoria": categoria,
    })


def salarios(request):
    """RF13 — cálculo e consulta dos salários dos professores."""
    form = CalculoSalarioForm(request.GET or None)
    calculo = None
    if form.is_valid():
        ref = form.cleaned_data["mes"]
        calculo = calcular_salario(form.cleaned_data["professor"], ref.year, ref.month)
    pagos = Movimentacao.objects.filter(
        categoria=Movimentacao.Categoria.SALARIO
    ).select_related("professor")
    return render(request, "financeiro/salarios.html", {
        "form": form, "calculo": calculo, "pagina": _paginar(request, pagos),
    })


def registrar_salario(request):
    """RF13 + RF07 — registra o salário calculado como saída financeira."""
    initial = {
        "categoria": Movimentacao.Categoria.SALARIO,
        "professor": request.GET.get("professor"),
        "valor": request.GET.get("valor"),
        "referencia": request.GET.get("referencia"),
        "descricao": request.GET.get("descricao", ""),
    }
    return _salvar_movimentacao(request, SaidaForm, "Registrar pagamento de salário",
                                initial=initial, sucesso="Salário registrado como saída.",
                                voltar=reverse("financeiro:salarios"))
