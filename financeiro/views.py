from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from escoladedanca.utils import ler_data, ler_mes, redirecionar

from .forms import (CalculoSalarioForm, CancelamentoCobrancaForm, EntradaForm, EstornoForm,
                    FiltroMovimentacoesForm, MensalidadeForm, RecebimentoForm, SaidaForm)
from .models import Cobranca, Movimentacao
from .services import (balanco_mensal, calcular_salario, calcular_saldo, estornar,
                       filtrar_movimentacoes, gerar_cobrancas, periodo_do_mes, receber,
                       resumir_cobrancas)

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
        ano, mes = ler_mes(request.GET.get("mes", ""))
    except ValueError:
        ano, mes = hoje.year, hoje.month
    return render(request, "financeiro/balanco.html", {
        "balanco": balanco_mensal(ano, mes),
        "mes_valor": f"{mes:02d}/{ano:04d}",
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


def _bloquear_vinculado(request, mov):
    """Recebimentos de cobrança e estornos não são editados nem excluídos:
    a correção é feita por estorno, preservando o histórico."""
    if mov.cobranca_id or mov.estorno_de_id:
        messages.error(request, "Este lançamento pertence a uma cobrança. Para corrigir, "
                                "use o estorno em Mensalidades.")
        alvo = mov.cobranca_id or mov.estorno_de.cobranca_id
        return redirect("financeiro:cobranca", alvo)
    return None


def editar(request, pk):
    mov = get_object_or_404(Movimentacao, pk=pk)
    if bloqueio := _bloquear_vinculado(request, mov):
        return bloqueio
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
    if bloqueio := _bloquear_vinculado(request, mov):
        return bloqueio
    if request.method == "POST":
        mov.delete()
        messages.success(request, "Movimentação excluída.")
        return redirect("financeiro:movimentacoes")
    return render(request, "confirmar_exclusao.html", {
        "objeto": mov, "voltar": reverse("financeiro:movimentacoes"),
    })


def _competencia(request):
    hoje = timezone.localdate()
    try:
        ano, mes = ler_mes(request.GET.get("mes", "") or request.POST.get("mes", ""))
        return date(ano, mes, 1)
    except ValueError:
        return hoje.replace(day=1)


def mensalidades(request):
    """RF11 — cobranças de mensalidade (situação informativa, RN08).

    Filtra por competência (mês) ou por período de vencimento (de/até, usado
    pelos links do Relatório) e por situação; os atalhos de situação mostram
    a contagem de cada uma no recorte escolhido.
    """
    from urllib.parse import urlencode
    hoje = timezone.localdate()
    competencia = _competencia(request)
    try:
        inicio = ler_data(request.GET.get("inicio", ""))
        fim = ler_data(request.GET.get("fim", ""))
    except ValueError:
        messages.error(request, "Data inválida no período; mostrando a competência.")
        inicio = fim = None
    por_periodo = bool(inicio and fim and inicio <= fim)
    qs = Cobranca.objects.com_totais().select_related("aluno", "matricula__turma__modalidade")
    if por_periodo:
        qs = qs.filter(vencimento__range=(inicio, fim)).order_by("vencimento", "aluno__nome")
    else:
        qs = qs.filter(competencia=competencia)
        _, ultimo = periodo_do_mes(competencia.year, competencia.month)
        inicio, fim = competencia, ultimo
    aluno_id = request.GET.get("aluno", "")
    if aluno_id.isdigit():
        qs = qs.filter(aluno_id=aluno_id)
    todas = list(qs)
    for c in todas:
        c.situacao_atual = c.situacao(hoje)
    resumo = resumir_cobrancas(todas, hoje)
    contagem = {v: 0 for v in Cobranca.Situacao.values}
    for c in todas:
        contagem[c.situacao_atual] += 1
    situacao = request.GET.get("situacao", "")
    cobrancas = [c for c in todas if c.situacao_atual == situacao] if situacao in contagem else todas

    base = {"aluno": aluno_id} if aluno_id.isdigit() else {}
    if por_periodo:
        base.update(inicio=f"{inicio:%d/%m/%Y}", fim=f"{fim:%d/%m/%Y}")
    else:
        base["mes"] = f"{competencia:%m/%Y}"
    atalhos = [{"valor": "", "rotulo": "Todas", "qtd": len(todas), "url": "?" + urlencode(base)}]
    for valor, rotulo in Cobranca.Situacao.choices:
        atalhos.append({"valor": valor, "rotulo": rotulo, "qtd": contagem[valor],
                        "url": "?" + urlencode({**base, "situacao": valor})})
    exportar = {"inicio": f"{inicio:%d/%m/%Y}", "fim": f"{fim:%d/%m/%Y}", "exportar": "cobrancas"}
    if situacao in contagem:
        exportar["situacao"] = situacao
    if aluno_id.isdigit():
        exportar["aluno"] = aluno_id
    return render(request, "financeiro/mensalidades.html", {
        "cobrancas": cobrancas, "resumo": resumo, "situacao": situacao, "atalhos": atalhos,
        "aluno_id": aluno_id, "por_periodo": por_periodo,
        "inicio": inicio, "fim": fim,
        "competencia": competencia, "mes_valor": f"{competencia:%m/%Y}",
        "mes_nome": f"{MESES[competencia.month - 1]} de {competencia.year}",
        "url_exportar": reverse("consultas:relatorios") + "?" + urlencode(exportar),
    })


@require_POST
def gerar_cobrancas_view(request):
    competencia = _competencia(request)
    n = gerar_cobrancas(competencia)
    if n:
        messages.success(request, f"{n} cobrança{'s' if n > 1 else ''} gerada{'s' if n > 1 else ''} "
                                  f"para {competencia:%m/%Y}. O caixa só muda quando houver recebimento.")
    else:
        messages.warning(request, f"As cobranças de {competencia:%m/%Y} já estavam geradas.")
    return redirect(f"{reverse('financeiro:mensalidades')}?mes={competencia:%m/%Y}")


def cobranca(request, pk):
    """Detalhe da cobrança: recebimentos, estornos e recebimento de novo valor."""
    c = get_object_or_404(Cobranca.objects.select_related("aluno", "matricula__turma"), pk=pk)
    form = None
    if c.saldo > 0:
        form = RecebimentoForm(request.POST or None, cobranca=c)
        if request.method == "POST" and form.is_valid():
            receber(c, form.cleaned_data["valor"], form.cleaned_data["data_pagamento"],
                    form.cleaned_data["forma_pagamento"])
            messages.success(request, "Recebimento registrado.")
            return redirect("financeiro:cobranca", c.pk)
    return render(request, "financeiro/cobranca.html", {
        "c": c, "form": form, "situacao": c.get_situacao_display(),
        "recebimentos": c.recebimentos.select_related("estorno").order_by("data_pagamento", "pk"),
        "estorno_form": EstornoForm(), "cancelar_form": CancelamentoCobrancaForm(),
    })


@require_POST
def estornar_view(request, pk):
    mov = get_object_or_404(Movimentacao, pk=pk, cobranca__isnull=False)
    form = EstornoForm(request.POST)
    if form.is_valid():
        try:
            estornar(mov, form.cleaned_data["motivo"])
            messages.success(request, "Recebimento estornado com o motivo registrado.")
        except ValueError as erro:
            messages.error(request, str(erro))
    else:
        messages.error(request, "Informe o motivo do estorno.")
    return redirect("financeiro:cobranca", mov.cobranca_id)


@require_POST
def cancelar_cobranca(request, pk):
    c = get_object_or_404(Cobranca, pk=pk)
    form = CancelamentoCobrancaForm(request.POST)
    if c.recebido > 0:
        messages.error(request, "A cobrança tem recebimentos. Estorne-os antes de cancelar.")
    elif not form.is_valid():
        messages.error(request, "Informe o motivo do cancelamento.")
    else:
        c.cancelada = True
        c.motivo_cancelamento = form.cleaned_data["motivo"]
        c.save(update_fields=["cancelada", "motivo_cancelamento"])
        messages.success(request, "Cobrança cancelada.")
    return redirect("financeiro:cobranca", c.pk)


def nova_mensalidade(request):
    """RF11 / RN06 — registra a mensalidade como entrada financeira (fluxo 10)."""
    initial = {}
    if request.GET.get("aluno", "").isdigit():
        initial["aluno"] = request.GET["aluno"]
    return _salvar_movimentacao(request, MensalidadeForm, "Mensalidade avulsa (sem cobrança)",
                                initial=initial, sucesso="Mensalidade avulsa registrada.",
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
