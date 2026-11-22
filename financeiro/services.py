"""Regras de cálculo financeiro (RF13, RF15, RF16 / RN05, RN07)."""
import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from aulas.models import Matricula

from .models import Cobranca, Movimentacao

ZERO = Decimal("0.00")


def _soma(qs) -> Decimal:
    return qs.aggregate(total=Sum("valor"))["total"] or ZERO


def periodo_do_mes(ano: int, mes: int) -> tuple[date, date]:
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, 1), date(ano, mes, ultimo)


def calcular_saldo(ate: date | None = None) -> dict:
    """RF15 — soma as entradas e subtrai as saídas registradas (fluxo 12)."""
    qs = Movimentacao.objects.all()
    if ate:
        qs = qs.filter(data_pagamento__lte=ate)
    entradas = _soma(qs.filter(tipo=Movimentacao.Tipo.ENTRADA))
    saidas = _soma(qs.filter(tipo=Movimentacao.Tipo.SAIDA))
    return {"entradas": entradas, "saidas": saidas, "saldo": entradas - saidas}


@dataclass
class BalancoMensal:
    ano: int
    mes: int
    total_entradas: Decimal = ZERO
    total_saidas: Decimal = ZERO
    entradas_por_origem: list = field(default_factory=list)
    entradas_por_forma: list = field(default_factory=list)
    saidas_por_categoria: list = field(default_factory=list)
    quantidade: int = 0

    @property
    def saldo(self) -> Decimal:
        return self.total_entradas - self.total_saidas

    @property
    def tem_movimentacoes(self) -> bool:
        return self.quantidade > 0


def _agrupar(qs, campo, choices):
    rotulos = dict(choices)
    linhas = qs.values(campo).annotate(total=Sum("valor"), qtd=Count("id")).order_by("-total")
    return [
        {"rotulo": rotulos.get(l[campo], l[campo] or "—"), "total": l["total"], "qtd": l["qtd"]}
        for l in linhas
    ]


def balanco_mensal(ano: int, mes: int) -> BalancoMensal:
    """RF16 / RN05 — compara as entradas e saídas realizadas no mês (fluxo 13)."""
    inicio, fim = periodo_do_mes(ano, mes)
    qs = Movimentacao.objects.filter(data_pagamento__range=(inicio, fim))
    entradas = qs.filter(tipo=Movimentacao.Tipo.ENTRADA)
    saidas = qs.filter(tipo=Movimentacao.Tipo.SAIDA)
    return BalancoMensal(
        ano=ano,
        mes=mes,
        total_entradas=_soma(entradas),
        total_saidas=_soma(saidas),
        entradas_por_origem=_agrupar(entradas, "origem", Movimentacao.Origem.choices),
        entradas_por_forma=_agrupar(
            entradas, "forma_pagamento", Movimentacao.FormaPagamento.choices
        ),
        saidas_por_categoria=_agrupar(saidas, "categoria", Movimentacao.Categoria.choices),
        quantidade=qs.count(),
    )


@dataclass
class CalculoSalario:
    professor: object
    ano: int
    mes: int
    inscricoes: int
    valor_por_aluno: Decimal
    ja_pago: Decimal
    por_aula: list = field(default_factory=list)

    @property
    def valor(self) -> Decimal:
        return (self.valor_por_aluno * self.inscricoes).quantize(Decimal("0.01"))

    @property
    def referencia(self) -> date:
        return date(self.ano, self.mes, 1)

    @property
    def pendente(self) -> Decimal:
        return max(self.valor - self.ja_pago, ZERO)


def calcular_salario(professor, ano: int, mes: int) -> CalculoSalario:
    """RF13 / RN07 — remuneração baseada nos alunos inscritos (matriculados).

    Salário do mês = inscrições ativas no mês nas aulas do professor × valor por
    aluno cadastrado no professor. Cada par aluno–aula conta uma vez: um aluno
    inscrito em duas aulas do mesmo professor conta duas vezes; um aluno que saiu
    e voltou para a mesma aula no mês conta uma vez. Alunos avulsos (sem
    matrícula) não entram no cálculo.
    """
    inicio, fim = periodo_do_mes(ano, mes)
    pares = (
        Matricula.ativas_no_periodo(inicio, fim)
        .filter(turma__professor=professor)
        .order_by()  # sem a ordenação padrão, que quebraria o DISTINCT
        .values("turma_id", "aluno_id")
        .distinct()
    )
    por_turma = {}
    for par in pares:
        por_turma[par["turma_id"]] = por_turma.get(par["turma_id"], 0) + 1
    from aulas.models import Turma

    turmas = Turma.objects.in_bulk(list(por_turma)).values()
    por_aula = sorted(
        ({"turma": t, "inscritos": por_turma[t.pk],
          "valor": (professor.valor_por_aluno * por_turma[t.pk]).quantize(Decimal("0.01"))}
         for t in turmas),
        key=lambda l: (l["turma"].dia_semana, l["turma"].hora_inicio),
    )
    ja_pago = _soma(
        Movimentacao.objects.filter(
            tipo=Movimentacao.Tipo.SAIDA,
            categoria=Movimentacao.Categoria.SALARIO,
            professor=professor,
            referencia=date(ano, mes, 1),
        )
    )
    return CalculoSalario(
        professor=professor,
        ano=ano,
        mes=mes,
        inscricoes=sum(por_turma.values()),
        valor_por_aluno=professor.valor_por_aluno,
        ja_pago=ja_pago,
        por_aula=por_aula,
    )


def filtrar_movimentacoes(qs, *, inicio=None, fim=None, tipo=None, q=None):
    """RF14 — filtro por período / tipo / texto (fluxo 12)."""
    if inicio:
        qs = qs.filter(data_pagamento__gte=inicio)
    if fim:
        qs = qs.filter(data_pagamento__lte=fim)
    if tipo in Movimentacao.Tipo.values:
        qs = qs.filter(tipo=tipo)
    if q:
        qs = qs.filter(
            Q(descricao__icontains=q) | Q(aluno__nome__icontains=q) | Q(professor__nome__icontains=q)
        )
    return qs


# ---------------------------------------------------------------------------
# Cobranças de mensalidade
# ---------------------------------------------------------------------------
def vencimento_da(competencia: date) -> date:
    ultimo = calendar.monthrange(competencia.year, competencia.month)[1]
    dia = min(max(int(getattr(settings, "ESCOLA_DIA_VENCIMENTO", 5)), 1), ultimo)
    return date(competencia.year, competencia.month, dia)


@transaction.atomic
def gerar_cobrancas(competencia: date) -> int:
    """Gera uma cobrança por matrícula ativa na competência (idempotente).

    Entram as matrículas em aberto, iniciadas até o fim do mês, de aulas ativas
    e com mensalidade final maior que zero. Não altera o caixa.
    """
    competencia = competencia.replace(day=1)
    _, fim = periodo_do_mes(competencia.year, competencia.month)
    ja_geradas = set(Cobranca.objects.filter(competencia=competencia)
                     .values_list("matricula_id", flat=True))
    novas = []
    for m in (Matricula.objects.filter(data_fim__isnull=True, data_inicio__lte=fim,
                                       turma__ativa=True)
              .exclude(pk__in=ja_geradas).select_related("turma")):
        if m.valor_final > 0:
            novas.append(Cobranca(matricula=m, aluno_id=m.aluno_id, competencia=competencia,
                                  valor=m.valor_final, vencimento=vencimento_da(competencia)))
    Cobranca.objects.bulk_create(novas)
    return len(novas)


@dataclass
class ResumoCobrancas:
    previsto: Decimal = ZERO
    recebido: Decimal = ZERO
    em_aberto: Decimal = ZERO
    atrasado: Decimal = ZERO
    quantidade: int = 0
    atrasadas: int = 0


def resumir_cobrancas(cobrancas, hoje=None) -> ResumoCobrancas:
    hoje = hoje or timezone.localdate()
    r = ResumoCobrancas()
    for c in cobrancas:
        if c.cancelada:
            continue
        r.quantidade += 1
        r.previsto += c.valor
        r.recebido += c.recebido
        r.em_aberto += c.saldo
        if c.situacao(hoje) == Cobranca.Situacao.ATRASADA or (c.saldo and c.vencimento < hoje):
            r.atrasado += c.saldo
            r.atrasadas += 1
    return r


@transaction.atomic
def receber(cobranca: Cobranca, valor: Decimal, data_pagamento: date, forma: str) -> Movimentacao:
    """Registra o recebimento (total ou parcial) como entrada de mensalidade."""
    if not (0 < valor <= cobranca.saldo):
        raise ValueError("O valor deve ser maior que zero e no máximo o saldo da cobrança.")
    _, fim = periodo_do_mes(cobranca.competencia.year, cobranca.competencia.month)
    mov = Movimentacao(
        tipo=Movimentacao.Tipo.ENTRADA, origem=Movimentacao.Origem.MENSALIDADE,
        aluno_id=cobranca.aluno_id, cobranca=cobranca, valor=valor,
        data_pagamento=data_pagamento, forma_pagamento=forma,
        validade=max(fim, data_pagamento),
        descricao=f"Mensalidade {cobranca.competencia:%m/%Y} — {cobranca.matricula.turma.nome or cobranca.matricula.turma.modalidade}",
    )
    mov.full_clean()
    mov.save()
    return mov


@transaction.atomic
def estornar(recebimento: Movimentacao, motivo: str, data: date | None = None) -> Movimentacao:
    """Estorna um recebimento: lança uma saída de estorno e preserva o histórico."""
    if not recebimento.cobranca_id or hasattr(recebimento, "estorno"):
        raise ValueError("Só recebimentos de cobrança ainda não estornados podem ser estornados.")
    motivo = " ".join((motivo or "").split())
    if not motivo:
        raise ValueError("Informe o motivo do estorno.")
    saida = Movimentacao(
        tipo=Movimentacao.Tipo.SAIDA, categoria=Movimentacao.Categoria.ESTORNO,
        estorno_de=recebimento, valor=recebimento.valor,
        data_pagamento=data or timezone.localdate(),
        forma_pagamento=recebimento.forma_pagamento,
        descricao=f"Estorno — {motivo}"[:200],
    )
    saida.full_clean()
    saida.save()
    return saida
