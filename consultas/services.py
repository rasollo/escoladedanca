"""Consulta de frequência e oportunidades de promoção.

Tudo é calculado a partir das chamadas (Presenca) e do vínculo dos alunos
(Matricula); o módulo não grava nada.

Métrica central — ocupação real: média de alunos *presentes* por aula dividida
pela capacidade da sala. Usamos presença, e não inscrição, porque inscrito que
não aparece não ocupa lugar (sistemas como Mindbody, Zenoti e ClassPass medem a
"utilização" da mesma forma).

A ocupação vira uma "temperatura":
    quente  ≥ 85%  turma quase lotada: não precisa de promoção
    morna   ≥ 70%  ocupação saudável (faixa recomendada pelo mercado: 70–85%)
    fria    ≥ 40%  sobram lugares: boa candidata a promoção
    gelada  < 40%  ocupação baixa: promoção forte ou rever dia/horário
Os limites podem ser ajustados em settings.CONSULTAS_FAIXAS.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.conf import settings
from django.db.models import Count, Exists, OuterRef, Q
from django.utils import timezone

from aulas.models import Matricula, Presenca, Turma

PERIODOS = (4, 8, 12, 26)  # semanas
PERIODO_PADRAO = 8

FAIXAS_PADRAO = {"quente": 85, "morna": 70, "fria": 40}

ROTULOS = {
    "quente": ("Quente", "🔥"),
    "morna": ("Morna", "🌤️"),
    "fria": ("Fria", "❄️"),
    "gelada": ("Gelada", "🧊"),
    "sem_dados": ("Sem dados", "—"),
}

# Variação entre a 1ª e a 2ª metade do período considerada relevante (%).
QUEDA_RELEVANTE = -15
ALTA_RELEVANTE = 15
FREQUENCIA_BAIXA = 70     # % de presença entre os registros da chamada
AVULSOS_RELEVANTE = 20    # % das presenças vindas de alunos não inscritos
MIN_AULAS_TENDENCIA = 4


def faixas() -> dict:
    return {**FAIXAS_PADRAO, **getattr(settings, "CONSULTAS_FAIXAS", {})}


def classificar(ocupacao: float | None) -> str:
    if ocupacao is None:
        return "sem_dados"
    f = faixas()
    if ocupacao >= f["quente"]:
        return "quente"
    if ocupacao >= f["morna"]:
        return "morna"
    if ocupacao >= f["fria"]:
        return "fria"
    return "gelada"


def periodo(semanas: int, hoje: date | None = None) -> tuple[date, date]:
    fim = hoje or timezone.localdate()
    return fim - timedelta(weeks=semanas) + timedelta(days=1), fim


@dataclass
class IndicadorTurma:
    turma: Turma
    inscritos: int
    aulas: int = 0                 # aulas com chamada registrada no período
    presencas: int = 0
    faltas: int = 0
    avulsos: int = 0               # presenças de alunos não inscritos na aula
    serie: list = field(default_factory=list)   # [(data, presentes)] em ordem

    @property
    def capacidade(self) -> int:
        return self.turma.sala.capacidade

    @property
    def media(self) -> float | None:
        return self.presencas / self.aulas if self.aulas else None

    @property
    def ocupacao(self) -> float | None:
        if self.media is None or not self.capacidade:
            return None
        return 100 * self.media / self.capacidade

    @property
    def ocupacao_inscricao(self) -> float:
        return 100 * self.inscritos / self.capacidade if self.capacidade else 0

    @property
    def lugares_livres(self) -> float:
        """Lugares vazios por aula (a aula é semanal, então também por semana)."""
        if self.media is None:
            return float(self.capacidade)
        return max(self.capacidade - self.media, 0)

    @property
    def frequencia(self) -> float | None:
        total = self.presencas + self.faltas
        return 100 * self.presencas / total if total else None

    @property
    def pct_avulsos(self) -> float:
        return 100 * self.avulsos / self.presencas if self.presencas else 0

    @property
    def tendencia(self) -> float | None:
        """Variação (%) da média de presentes: 2ª metade vs 1ª metade do período."""
        if len(self.serie) < MIN_AULAS_TENDENCIA:
            return None
        valores = [p for _, p in self.serie]
        meio = len(valores) // 2
        antes = sum(valores[:meio]) / meio
        depois = sum(valores[meio:]) / (len(valores) - meio)
        if not antes:
            return None
        return 100 * (depois - antes) / antes

    @property
    def tendencia_abs(self) -> float | None:
        return None if self.tendencia is None else abs(self.tendencia)

    @property
    def faixa(self) -> str:
        return classificar(self.ocupacao)

    @property
    def faixa_rotulo(self) -> str:
        return ROTULOS[self.faixa][0]

    @property
    def faixa_icone(self) -> str:
        return ROTULOS[self.faixa][1]

    @property
    def termometro(self) -> float:
        """Posição do marcador no termômetro (0–100)."""
        return round(min(self.ocupacao or 0, 100))

    @property
    def serie_barras(self) -> list:
        """Série para o mini-gráfico: [(data, presentes, altura %)]."""
        return [(d, p, round(100 * p / self.capacidade) if self.capacidade else 0)
                for d, p in self.serie]

    @property
    def acao(self) -> str:
        return {
            "quente": "Sem promoção — avaliar nova turma",
            "morna": "Manter",
            "fria": "Promoção leve",
            "gelada": "Promoção forte / rever horário",
            "sem_dados": "Registrar chamadas",
        }[self.faixa]

    @property
    def recomendacoes(self) -> list[str]:
        nome = self.turma.modalidade.nome
        livres = round(self.lugares_livres)
        r = []
        if self.faixa == "sem_dados":
            return ["Nenhuma chamada registrada no período: sem chamada não há como medir a ocupação."]
        if self.faixa == "quente":
            r.append(f"Quase lotada ({self.ocupacao:.0f}% de ocupação). Não precisa de promoção; "
                     f"há demanda para abrir outra turma de {nome} ou rever o valor.")
        elif self.faixa == "morna":
            r.append(f"Ocupação saudável ({self.ocupacao:.0f}%). Ainda cabem cerca de {livres} "
                     "alunos por aula; promoções só pontuais.")
        elif self.faixa == "fria":
            r.append(f"Sobram cerca de {livres} lugares por aula. Boa candidata a promoção: "
                     "aula experimental grátis, \"traga um amigo\" ou pacote com desconto neste horário.")
        else:
            r.append(f"Só {self.ocupacao:.0f}% de ocupação ({livres} lugares vazios por aula). "
                     "Promoção forte, ou avaliar mudar o dia/horário ou juntar com outra turma.")
        t = self.tendencia
        if t is not None and t <= QUEDA_RELEVANTE:
            r.append(f"A presença caiu {abs(t):.0f}% na segunda metade do período: agir antes que esfrie mais.")
        elif t is not None and t >= ALTA_RELEVANTE and self.faixa in ("fria", "gelada"):
            r.append(f"A presença subiu {t:.0f}% no período: a turma está aquecendo, "
                     "talvez baste divulgar mais.")
        if self.frequencia is not None and self.frequencia < FREQUENCIA_BAIXA:
            r.append(f"Frequência de {self.frequencia:.0f}%: muitos alunos registrados faltam. "
                     "Aqui o problema é engajamento, não vaga — vale contatar os faltosos.")
        if self.pct_avulsos >= AVULSOS_RELEVANTE:
            r.append(f"{self.pct_avulsos:.0f}% das presenças são de alunos avulsos (sem inscrição): "
                     "ofereça a eles um pacote de adesão.")
        return r


def indicadores_por_turma(inicio: date, fim: date) -> list[IndicadorTurma]:
    turmas = (Turma.objects.filter(ativa=True)
              .select_related("modalidade", "sala", "professor")
              .annotate(qtd_inscritos=Count("alunos")))
    ind = {t.pk: IndicadorTurma(turma=t, inscritos=t.qtd_inscritos) for t in turmas}

    inscrito_na_data = Matricula.objects.filter(
        turma_id=OuterRef("turma_id"), aluno_id=OuterRef("aluno_id"),
        data_inicio__lte=OuterRef("data"),
    ).filter(Q(data_fim__isnull=True) | Q(data_fim__gte=OuterRef("data")))
    registros = (Presenca.objects.filter(turma_id__in=ind, data__range=(inicio, fim))
                 .annotate(inscrito=Exists(inscrito_na_data))
                 .values_list("turma_id", "data", "presente", "inscrito"))

    por_aula = defaultdict(int)
    datas = defaultdict(set)
    for turma_id, data, presente, inscrito in registros:
        i = ind[turma_id]
        datas[turma_id].add(data)
        if presente:
            i.presencas += 1
            por_aula[turma_id, data] += 1
            if not inscrito:
                i.avulsos += 1
        else:
            i.faltas += 1
    for turma_id, ds in datas.items():
        ind[turma_id].aulas = len(ds)
        ind[turma_id].serie = [(d, por_aula[turma_id, d]) for d in sorted(ds)]
    return list(ind.values())


def presencas_por_semana(inicio: date, fim: date) -> list[dict]:
    """Ocupação de cada semana: presentes ÷ lugares das aulas que tiveram chamada.

    Comparar semanas pelo total de presenças engana: uma semana com feriado ou
    com chamada esquecida tem menos aulas, e o total cai sem que a frequência
    tenha caído. Em porcentagem, as semanas ficam comparáveis.
    """
    qtd = (fim - inicio).days // 7 + 1
    semanas = [{"inicio": inicio + timedelta(weeks=n), "presencas": 0, "faltas": 0,
                "aulas": set(), "lugares": 0} for n in range(qtd)]
    registros = (Presenca.objects.filter(turma__ativa=True, data__range=(inicio, fim))
                 .values_list("turma_id", "data", "presente", "turma__sala__capacidade"))
    for turma_id, data, presente, capacidade in registros:
        s = semanas[(data - inicio).days // 7]
        if (turma_id, data) not in s["aulas"]:
            s["aulas"].add((turma_id, data))
            s["lugares"] += capacidade or 0
        s["presencas" if presente else "faltas"] += 1
    for s in semanas:
        s["aulas"] = len(s["aulas"])
        registrados = s["presencas"] + s["faltas"]
        s["ocupacao"] = 100 * s["presencas"] / s["lugares"] if s["lugares"] else None
        s["frequencia"] = 100 * s["presencas"] / registrados if registrados else None
        s["faixa"] = classificar(s["ocupacao"])
        s["altura"] = round(min(s["ocupacao"] or 0, 100))
    return semanas


def por_modalidade(indicadores) -> list[dict]:
    grupos = defaultdict(lambda: {"turmas": 0, "presencas": 0, "lugares": 0, "inscritos": 0})
    for i in indicadores:
        g = grupos[i.turma.modalidade.nome]
        g["turmas"] += 1
        g["presencas"] += i.presencas
        g["lugares"] += i.aulas * i.capacidade
        g["inscritos"] += i.inscritos
    linhas = []
    for nome, g in grupos.items():
        ocupacao = 100 * g["presencas"] / g["lugares"] if g["lugares"] else None
        linhas.append({"nome": nome, **g, "ocupacao": ocupacao, "faixa": classificar(ocupacao),
                       "barra": round(min(ocupacao or 0, 100))})
    return sorted(linhas, key=lambda l: l["presencas"], reverse=True)


def mapa_de_calor(indicadores) -> dict:
    """Grade dia da semana × horário de início com as turmas de cada célula."""
    nomes_dias = dict(Turma.DiaSemana.choices)
    dias = sorted({i.turma.dia_semana for i in indicadores})
    horas = sorted({i.turma.hora_inicio for i in indicadores})
    celulas = defaultdict(list)
    for i in indicadores:
        celulas[i.turma.hora_inicio, i.turma.dia_semana].append(i)
    return {
        "dias": [nomes_dias[d].split("-")[0] for d in dias],
        "linhas": [{"hora": h, "celulas": [celulas.get((h, d), []) for d in dias]} for h in horas],
    }


def consulta(semanas: int = PERIODO_PADRAO, hoje: date | None = None) -> dict:
    inicio, fim = periodo(semanas, hoje)
    indicadores = indicadores_por_turma(inicio, fim)
    com_dados = [i for i in indicadores if i.aulas]

    presencas = sum(i.presencas for i in com_dados)
    lugares = sum(i.aulas * i.capacidade for i in com_dados)
    # Ordena pela ocupação (e não pela média de presentes) para comparar salas de
    # capacidades diferentes; a barra usa a escala absoluta de 0 a 100%.
    ranking = sorted(com_dados, key=lambda i: i.ocupacao or 0, reverse=True)
    contagem = defaultdict(int)
    for i in indicadores:
        contagem[i.faixa] += 1

    return {
        "semanas": semanas,
        "periodos": PERIODOS,
        "inicio": inicio,
        "fim": fim,
        "faixas": faixas(),
        "indicadores": indicadores,
        "ranking": ranking,
        # Promoção: turmas frias/geladas, da mais vazia para a menos vazia.
        "oportunidades": sorted((i for i in com_dados if i.faixa in ("fria", "gelada")),
                                key=lambda i: i.ocupacao),
        # Turmas que estão esfriando mesmo sem estar frias ainda.
        "esfriando": [i for i in com_dados if i.faixa in ("quente", "morna")
                      and i.tendencia is not None and i.tendencia <= QUEDA_RELEVANTE],
        "lotando": [i for i in com_dados if i.faixa == "quente"],
        "sem_dados": [i for i in indicadores if not i.aulas],
        "modalidades": por_modalidade(com_dados),
        "semanal": presencas_por_semana(inicio, fim),
        "mapa": mapa_de_calor(indicadores),
        "resumo": {
            "ocupacao": 100 * presencas / lugares if lugares else None,
            "faixa": classificar(100 * presencas / lugares if lugares else None),
            "presencas": presencas,
            "aulas": sum(i.aulas for i in com_dados),
            "lugares_livres": round(sum(i.lugares_livres for i in com_dados)),
            "contagem": dict(contagem),
        },
    }
