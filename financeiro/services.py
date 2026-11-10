"""Regras de cálculo financeiro (RF13, RF15, RF16 / RN05, RN07)."""
import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum

from aulas.models import Matricula

from .models import Movimentacao

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
