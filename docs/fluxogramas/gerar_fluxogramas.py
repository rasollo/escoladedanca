"""Gera os fluxogramas do Portal da Dança (versão 1.0).

Uma única descrição de cada fluxo produz:
  * Portal_da_Danca_Fluxogramas_v1.0.drawio  — uma aba por fluxo, editável no draw.io
  * svg/NN.svg                             — desenho de cada fluxo
  * Portal_da_Danca_Fluxogramas_v1.0.pdf     — via LibreOffice + pdfunite (se disponíveis)

Uso:  python3 docs/fluxogramas/gerar_fluxogramas.py
Somente biblioteca padrão.
"""
import html
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PASTA = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Geometria
# ---------------------------------------------------------------------------
COL_W, ROW_H = 250, 116
X0, Y0 = 90, 118  # margem esquerda (espaço para laços) e topo (título)
SIZES = {"start": (120, 42), "end": (120, 42), "proc": (204, 56), "io": (214, 56), "dec": (214, 88)}
WRAP = {"start": 18, "end": 18, "proc": 32, "io": 30, "dec": 22}
FONT = 11.5
SKEW = 16

CORES = {
    "start": ("#e3f2ea", "#2f7a55"), "end": ("#e3f2ea", "#2f7a55"),
    "proc": ("#eef1fa", "#4a5a8c"), "io": ("#f5effb", "#6a4a8c"), "dec": ("#fff4dc", "#a8761a"),
}
TINTA, LINHA, FUNDO = "#22202a", "#55536a", "#ffffff"


class No:
    def __init__(self, nid, kind, text, col, row):
        self.id, self.kind, self.text, self.col, self.row = nid, kind, text, col, row
        self.w, self.h = SIZES[kind]
        self.cx = X0 + col * COL_W + COL_W / 2
        self.cy = Y0 + row * ROW_H + ROW_H / 2

    @property
    def left(self): return self.cx - self.w / 2
    @property
    def right(self): return self.cx + self.w / 2
    @property
    def top(self): return self.cy - self.h / 2
    @property
    def bottom(self): return self.cy + self.h / 2

    def porta(self, lado):
        return {"T": (self.cx, self.top), "B": (self.cx, self.bottom),
                "L": (self.left, self.cy), "R": (self.right, self.cy)}[lado]


REL = {"T": (0.5, 0), "B": (0.5, 1), "L": (0, 0.5), "R": (1, 0.5)}


def wrap(texto, n):
    linhas, atual = [], ""
    for palavra in texto.split():
        if atual and len(atual) + 1 + len(palavra) > n:
            linhas.append(atual)
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    if atual:
        linhas.append(atual)
    return linhas


# ---------------------------------------------------------------------------
# Roteamento ortogonal
# ---------------------------------------------------------------------------
def rotear(s, d, via, nos, idx):
    """Devolve (porta_saida, porta_entrada, pontos)."""
    if via in ("L", "R"):
        r0, r1 = sorted((s.row, d.row))
        faixa = [n for n in nos if r0 <= n.row <= r1]
        if via == "L":
            x = min(n.left for n in faixa) - 30 - idx * 14
        else:
            x = max(n.right for n in faixa) + 30 + idx * 14
        a, b = s.porta(via), d.porta(via)
        return via, via, [a, (x, a[1]), (x, b[1]), b]
    lado = "R" if d.col > s.col else "L"
    if d.row > s.row:
        if s.col == d.col:
            return "B", "T", [s.porta("B"), d.porta("T")]
        if s.kind == "dec":
            a = s.porta(lado)
            return lado, "T", [a, (d.cx, a[1]), d.porta("T")]
        a, b = s.porta("B"), d.porta("T")
        jy = d.top - 20
        return "B", "T", [a, (a[0], jy), (b[0], jy), b]
    if d.row == s.row:
        a, b = s.porta(lado), d.porta("L" if lado == "R" else "R")
        return lado, ("L" if lado == "R" else "R"), [a, b]
    # d acima de s
    if s.col == d.col:
        return rotear(s, d, "R", nos, idx)
    if s.kind == "dec":
        a = s.porta(lado)
        return lado, "B", [a, (d.cx, a[1]), d.porta("B")]
    entrada = "R" if s.col > d.col else "L"
    a, b = s.porta("T"), d.porta(entrada)
    return "T", entrada, [a, (a[0], b[1]), b]


def posicao_rotulo(pts):
    (x1, y1), (x2, y2) = pts[0], pts[1]
    if abs(x2 - x1) > abs(y2 - y1):  # horizontal
        sinal = 1 if x2 > x1 else -1
        return x1 + sinal * 26, y1 - 6, "middle"
    sinal = 1 if y2 > y1 else -1
    return x1 + 8, y1 + sinal * 16 + (4 if sinal > 0 else 0), "start"


# ---------------------------------------------------------------------------
# Fluxos
# ---------------------------------------------------------------------------
FLUXOS = []


def fluxo(numero, titulo, requisitos, situacao, mudancas):
    def registrar(fn):
        nos, arestas = {}, []

        def n(nid, kind, text, col, row):
            nos[nid] = No(nid, kind, text, col, row)

        def e(a, b, rotulo="", via=None):
            arestas.append((a, b, rotulo, via))

        fn(n, e)
        FLUXOS.append({"numero": numero, "titulo": titulo, "requisitos": requisitos,
                       "situacao": situacao, "mudancas": mudancas, "nos": nos, "arestas": arestas})
        return fn
    return registrar


@fluxo("00", "Acesso ao sistema", "RF22, RF24, RNF03", "Novo",
       "Fluxo novo: login obrigatório (RNF03), registro de login, falha e logout com usuário e IP.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar uma página do sistema", 1, 1)
    n("d1", "dec", "Usuário já autenticado?", 1, 2)
    n("u", "io", "Informar usuário e senha", 2, 3)
    n("d2", "dec", "Usuário e senha válidos?", 2, 4)
    n("f", "proc", "Registrar LOGIN_FALHOU e exibir aviso", 3, 4)
    n("ok", "proc", "Registrar LOGIN_OK (usuário e IP)", 2, 5)
    n("p", "io", "Exibir página solicitada", 1, 6)
    n("r", "proc", "Registrar acesso (usuário, IP, página)", 1, 7)
    n("d3", "dec", "Clicou em Sair?", 1, 8)
    n("lo", "proc", "Registrar LOGOUT e encerrar sessão", 1, 9)
    n("fim", "end", "Fim", 1, 10)
    e("i", "a"); e("a", "d1"); e("d1", "p", "Sim"); e("d1", "u", "Não"); e("u", "d2")
    e("d2", "f", "Não"); e("f", "u"); e("d2", "ok", "Sim"); e("ok", "p"); e("p", "r")
    e("r", "d3"); e("d3", "a", "Não", "L"); e("d3", "lo", "Sim"); e("lo", "fim")


@fluxo("01", "Cadastro e consulta de alunos", "RF01, RF02, RN08", "Corrigido",
       "Correção: “Solicitar correção” volta para a entrada de dados (antes ia para “Cadastrar aluno”). Incluída a atualização dos dados.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar a área de alunos", 1, 1)
    n("d", "dec", "Escolher operação", 1, 2)
    n("c1", "io", "Informar dados do aluno (nome obrigatório)", 0, 3)
    n("c2", "dec", "Dados obrigatórios informados?", 0, 4)
    n("c3", "proc", "Solicitar correção dos dados", 1, 4)
    n("c4", "proc", "Cadastrar aluno", 0, 5)
    n("q1", "io", "Buscar por nome, e-mail ou telefone", 2, 3)
    n("q2", "io", "Exibir lista e selecionar aluno", 2, 4)
    n("q3", "dec", "Atualizar dados?", 2, 5)
    n("q4", "io", "Exibir dados, aulas, presenças e mensalidades", 2, 6)
    n("q5", "proc", "Editar, validar e salvar dados", 3, 6)
    n("fim", "end", "Fim", 1, 8)
    e("i", "a"); e("a", "d"); e("d", "c1", "Cadastrar"); e("d", "q1", "Consultar")
    e("c1", "c2"); e("c2", "c3", "Não"); e("c3", "c1"); e("c2", "c4", "Sim"); e("c4", "fim")
    e("q1", "q2"); e("q2", "q3"); e("q3", "q4", "Não"); e("q3", "q5", "Sim")
    e("q4", "fim"); e("q5", "fim")


@fluxo("02", "Cadastro, consulta e atualização de professores", "RF17, RN07", "Corrigido",
       "Correção: laço “Não: revisar” com seta única. Incluído o valor por aluno inscrito, base do salário.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar a área de professores", 1, 1)
    n("d", "dec", "Escolher operação", 1, 2)
    n("c1", "io", "Informar nome, contato e valor por aluno inscrito (R$/mês)", 0, 3)
    n("c2", "dec", "Dados completos e valor ≥ 0?", 0, 4)
    n("c3", "proc", "Revisar dados", 1, 4)
    n("c4", "proc", "Cadastrar professor", 0, 5)
    n("q1", "io", "Selecionar professor cadastrado", 2, 3)
    n("q2", "dec", "Consultar ou atualizar?", 2, 4)
    n("q3", "io", "Exibir dados, aulas e salário estimado do mês", 2, 5)
    n("q4", "io", "Editar dados", 3, 5)
    n("q5", "proc", "Salvar dados atualizados", 3, 6)
    n("fim", "end", "Fim", 1, 8)
    e("i", "a"); e("a", "d"); e("d", "c1", "Cadastrar"); e("d", "q1", "Consultar / atualizar")
    e("c1", "c2"); e("c2", "c3", "Não"); e("c3", "c1"); e("c2", "c4", "Sim"); e("c4", "fim")
    e("q1", "q2"); e("q2", "q3", "Consultar"); e("q2", "q4", "Atualizar"); e("q4", "q5")
    e("q3", "fim"); e("q5", "fim")


@fluxo("03", "Modalidades e salas", "RF18, RN09, RN15", "Corrigido",
       "Correção: “Selecionar operação” passou a ser decisão (losango). Incluídas as salas e o bloqueio de remoção quando há aula usando o registro.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar modalidades e salas", 1, 1)
    n("d", "dec", "Selecionar operação", 1, 2)
    n("c1", "io", "Informar nome da modalidade ou sala (e capacidade)", 0, 3)
    n("c2", "dec", "Nome único e capacidade ≥ 1?", 0, 4)
    n("c3", "proc", "Exibir erro", 1, 4)
    n("c4", "proc", "Salvar cadastro", 0, 5)
    n("m1", "io", "Selecionar modalidade ou sala", 2, 3)
    n("m2", "dec", "Qual manutenção?", 2, 4)
    n("m3", "proc", "Atualizar dados", 2, 5)
    n("m4", "dec", "Usada por alguma aula agendada?", 3, 5)
    n("m5", "proc", "Remover registro", 3, 6)
    n("m6", "io", "Informar que não pode ser removido", 4, 6)
    n("fim", "end", "Fim", 1, 8)
    e("i", "a"); e("a", "d"); e("d", "c1", "Cadastrar"); e("d", "m1", "Atualizar / remover")
    e("c1", "c2"); e("c2", "c3", "Não"); e("c3", "c1"); e("c2", "c4", "Sim"); e("c4", "fim")
    e("m1", "m2"); e("m2", "m3", "Atualizar"); e("m2", "m4", "Remover")
    e("m4", "m5", "Não"); e("m4", "m6", "Sim")
    e("m3", "fim"); e("m5", "fim"); e("m6", "fim")


@fluxo("04", "Agendamento de aulas", "RF19, RF20, RN09, RN10, RN13, RN14, RN15", "Corrigido",
       "Correção: verifica horário de funcionamento, choque de sala e de professor e capacidade; o ramo de erro volta para revisão; incluídos alterar, desativar e remover.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar agenda de aulas", 1, 1)
    n("d", "dec", "Nova aula ou aula existente?", 1, 2)
    n("nv", "proc", "Iniciar novo agendamento", 0, 3)
    n("ex", "io", "Selecionar aula existente", 2, 3)
    n("op", "dec", "Alterar, desativar ou remover?", 2, 4)
    n("dados", "io", "Informar modalidade, dia, horário, sala e professor", 1, 4)
    n("v1", "dec", "Entre 18h e 22h e término após o início?", 1, 5)
    n("v2", "dec", "Sala e professor livres no horário?", 1, 6)
    n("v3", "dec", "Inscritos cabem na sala (até 40)?", 1, 7)
    n("rev", "proc", "Revisar dados ou organizar outra turma", 0, 6)
    n("sv", "proc", "Salvar agendamento", 1, 8)
    n("ag", "io", "Aula disponível na agenda", 1, 9)
    n("des", "proc", "Desativar aula e encerrar as matrículas", 2, 5)
    n("rm", "dec", "Aula tem presenças ou matrículas?", 3, 5)
    n("rm1", "io", "Orientar a desativar (histórico protegido)", 3, 6)
    n("rm2", "proc", "Remover aula", 4, 6)
    n("fim", "end", "Fim", 1, 10)
    e("i", "a"); e("a", "d"); e("d", "nv", "Nova"); e("d", "ex", "Existente")
    e("nv", "dados"); e("ex", "op"); e("op", "dados", "Alterar")
    e("op", "des", "Desativar"); e("op", "rm", "Remover")
    e("dados", "v1"); e("v1", "rev", "Não"); e("v1", "v2", "Sim"); e("v2", "rev", "Não")
    e("v2", "v3", "Sim"); e("v3", "rev", "Não"); e("v3", "sv", "Sim"); e("rev", "dados", "", "L")
    e("sv", "ag"); e("ag", "fim")
    e("rm", "rm1", "Sim"); e("rm", "rm2", "Não")
    e("des", "fim"); e("rm1", "fim"); e("rm2", "fim")


@fluxo("05", "Matrícula de alunos nas aulas", "RF20, RF21, RF24, RN07, RN08, RN09", "Novo",
       "Fluxo novo: a inscrição abre uma matrícula com data de início; a saída encerra a matrícula com data de fim. É a base do salário (fluxo 11). Não é exigida para participar (RN08).")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "io", "Selecionar aula agendada", 1, 1)
    n("b", "io", "Exibir inscritos, capacidade da sala e vagas", 1, 2)
    n("c", "io", "Marcar alunos a inscrever e desmarcar os que saíram", 1, 3)
    n("d", "dec", "Total de inscritos ≤ capacidade da sala?", 1, 4)
    n("r", "proc", "Revisar seleção ou organizar outra turma", 2, 4)
    n("m1", "proc", "Abrir matrícula (início = hoje) de cada aluno marcado", 1, 5)
    n("m2", "proc", "Encerrar matrícula (fim = hoje) de cada aluno desmarcado", 1, 6)
    n("au", "proc", "Registrar a alteração na auditoria", 1, 7)
    n("s", "io", "Matrículas disponíveis para o cálculo do salário (fluxo 11)", 1, 8)
    n("fim", "end", "Fim", 1, 9)
    e("i", "a"); e("a", "b"); e("b", "c"); e("c", "d"); e("d", "r", "Não"); e("r", "c")
    e("d", "m1", "Sim"); e("m1", "m2"); e("m2", "au"); e("au", "s"); e("s", "fim")


@fluxo("06", "Registro de presença e faltas", "RF03, RF04, RF21, RN08", "Corrigido",
       "Correção: incluídos os alunos avulsos (sem matrícula), vários de uma vez, com opção de retirar um incluído por engano; validação do dia da aula e da capacidade. A consulta passou para o fluxo 07.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "io", "Selecionar aula agendada e data", 1, 1)
    n("d1", "dec", "Data cai no dia da semana da aula?", 1, 2)
    n("x", "proc", "Informar o dia correto da aula", 2, 2)
    n("b", "io", "Exibir alunos inscritos na aula", 1, 3)
    n("c", "io", "Marcar presente ou falta para cada aluno", 1, 4)
    n("d2", "dec", "Há alunos avulsos (sem matrícula)?", 1, 5)
    n("av", "io", "Adicionar um ou mais avulsos (botão +) ou retirar um incluído por engano", 2, 6)
    n("d3", "dec", "Presentes ≤ capacidade da sala?", 1, 7)
    n("rv", "proc", "Revisar marcações", 0, 7)
    n("s", "proc", "Salvar registros da aula (um por aluno e data)", 1, 8)
    n("fim", "end", "Fim", 1, 9)
    e("i", "a"); e("a", "d1"); e("d1", "x", "Não"); e("x", "a"); e("d1", "b", "Sim")
    e("b", "c"); e("c", "d2"); e("d2", "av", "Sim"); e("d2", "d3", "Não"); e("av", "d3")
    e("d3", "rv", "Não"); e("rv", "c", "", "L"); e("d3", "s", "Sim"); e("s", "fim")


@fluxo("07", "Consulta de presenças e faltas", "RF04", "Novo",
       "Fluxo novo, separado do 06: consulta com filtros por aluno, aula, situação e período.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar presenças e faltas", 1, 1)
    n("b", "io", "Filtrar por aluno, aula, situação e período (opcional)", 1, 2)
    n("d1", "dec", "Datas do filtro válidas?", 1, 3)
    n("x", "proc", "Avisar data inválida", 2, 3)
    n("c", "proc", "Buscar registros", 1, 4)
    n("d2", "dec", "Há registros?", 1, 5)
    n("s", "io", "Exibir lista com totais de presenças e faltas", 0, 6)
    n("v", "io", "Informar que não há registros", 2, 6)
    n("fim", "end", "Fim", 1, 7)
    e("i", "a"); e("a", "b"); e("b", "d1"); e("d1", "x", "Não"); e("x", "b"); e("d1", "c", "Sim")
    e("c", "d2"); e("d2", "s", "Sim"); e("d2", "v", "Não"); e("s", "fim"); e("v", "fim")


@fluxo("08", "Registro de entradas financeiras", "RF06, RF08, RF10, RN01, RN02, RN04, RN11, RN12", "Corrigido",
       "Correção: decisões em losango; ramo de erro na validação; origem mensalidade exige o aluno.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Iniciar registro de entrada", 1, 1)
    n("b", "io", "Informar valor e data do pagamento", 1, 2)
    n("c", "io", "Selecionar origem: mensalidade, aluguel de sala, bebidas ou camisetas", 1, 3)
    n("d1", "dec", "Origem é mensalidade?", 1, 4)
    n("al", "io", "Selecionar o aluno", 2, 5)
    n("f", "io", "Selecionar forma de pagamento: Pix, dinheiro ou cartão", 1, 6)
    n("v", "io", "Informar validade, se aplicável", 1, 7)
    n("d2", "dec", "Valor > 0 e validade ≥ data do pagamento?", 1, 8)
    n("er", "proc", "Exibir erros e corrigir", 0, 8)
    n("s", "proc", "Salvar entrada", 1, 9)
    n("m", "io", "Entrada disponível nas movimentações e no balanço", 1, 10)
    n("fim", "end", "Fim", 1, 11)
    e("i", "a"); e("a", "b"); e("b", "c"); e("c", "d1"); e("d1", "al", "Sim"); e("d1", "f", "Não")
    e("al", "f"); e("f", "v"); e("v", "d2"); e("d2", "er", "Não"); e("er", "b", "", "L")
    e("d2", "s", "Sim"); e("s", "m"); e("m", "fim")


@fluxo("09", "Registro de saídas financeiras", "RF07, RF09, RF10, RF12, RN01, RN03, RN04", "Corrigido",
       "Correção: o cálculo do salário saiu deste fluxo e virou o fluxo 11; a categoria vem de lista fechada; ramo de erro na validação.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Iniciar registro de saída", 1, 1)
    n("b", "io", "Informar valor e data do pagamento", 1, 2)
    n("c", "io", "Selecionar categoria: contas, manutenção, luz, água, taxas, Prefeitura ou salário", 1, 3)
    n("d1", "dec", "Categoria é salário de professor?", 1, 4)
    n("sal", "proc", "Usar o cálculo de salário (fluxo 11)", 2, 5)
    n("v", "io", "Informar validade e forma de pagamento, quando aplicável", 1, 5)
    n("d2", "dec", "Valor > 0 e validade ≥ data do pagamento?", 1, 6)
    n("er", "proc", "Exibir erros e corrigir", 0, 6)
    n("s", "proc", "Salvar saída", 1, 7)
    n("m", "io", "Despesa disponível na consulta financeira", 1, 8)
    n("fim", "end", "Fim", 1, 9)
    e("i", "a"); e("a", "b"); e("b", "c"); e("c", "d1"); e("d1", "sal", "Sim"); e("d1", "v", "Não")
    e("v", "d2"); e("d2", "er", "Não"); e("er", "b", "", "L"); e("d2", "s", "Sim"); e("s", "m")
    e("m", "fim"); e("sal", "fim")


@fluxo("10", "Mensalidades", "RF10, RF11, RN02, RN04, RN06, RN08, RN12", "Corrigido",
       "Correção: pede forma de pagamento e validade; registrar e consultar viraram opções; situação é só informativa (RN08).")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar mensalidades", 1, 1)
    n("d", "dec", "Registrar ou consultar?", 1, 2)
    n("r1", "io", "Selecionar aluno", 0, 3)
    n("r2", "io", "Informar valor, data, forma de pagamento e validade (sugestão: 1 mês)", 0, 4)
    n("r3", "dec", "Dados válidos?", 0, 5)
    n("r4", "proc", "Corrigir dados", 1, 5)
    n("r5", "proc", "Registrar como entrada (origem = mensalidade)", 0, 6)
    n("c1", "io", "Selecionar aluno (opcional)", 2, 3)
    n("c2", "dec", "Há mensalidade registrada?", 2, 4)
    n("c3", "io", "Exibir pagamentos e situação (informativa)", 2, 5)
    n("c4", "io", "Exibir ausência de registro", 3, 5)
    n("fim", "end", "Fim", 1, 8)
    e("i", "a"); e("a", "d"); e("d", "r1", "Registrar"); e("d", "c1", "Consultar")
    e("r1", "r2"); e("r2", "r3"); e("r3", "r4", "Não"); e("r4", "r2"); e("r3", "r5", "Sim")
    e("r5", "fim"); e("c1", "c2"); e("c2", "c3", "Sim"); e("c2", "c4", "Não")
    e("c3", "fim"); e("c4", "fim")


@fluxo("11", "Cálculo e pagamento do salário dos professores", "RF07, RF13, RN07, RN16", "Novo",
       "Fluxo novo: salário = alunos inscritos (matrículas ativas no mês) nas aulas do professor × valor por aluno. Cada par aluno–aula conta uma vez; avulsos não contam; faltas não reduzem o salário.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar salários", 1, 1)
    n("b", "io", "Selecionar professor e mês", 1, 2)
    n("c", "proc", "Buscar matrículas das aulas do professor ativas em algum dia do mês", 1, 3)
    n("d", "proc", "Contar inscrições: cada par aluno–aula conta 1", 1, 4)
    n("e", "proc", "Salário = inscrições × valor por aluno do professor", 1, 5)
    n("f", "io", "Exibir total e detalhamento por aula", 1, 6)
    n("g", "dec", "Já há salário registrado neste mês?", 1, 7)
    n("h", "io", "Exibir valor já pago e o que falta pagar", 2, 8)
    n("k", "dec", "Confirmar pagamento?", 1, 9)
    n("n", "proc", "Encerrar sem registrar", 0, 10)
    n("s", "proc", "Registrar saída: categoria salário, professor e mês de referência", 1, 10)
    n("t", "io", "Pagamento disponível nas despesas e no balanço", 1, 11)
    n("fim", "end", "Fim", 1, 12)
    e("i", "a"); e("a", "b"); e("b", "c"); e("c", "d"); e("d", "e"); e("e", "f"); e("f", "g")
    e("g", "h", "Sim"); e("g", "k", "Não"); e("h", "k"); e("k", "n", "Não"); e("k", "s", "Sim")
    e("s", "t"); e("t", "fim"); e("n", "fim")


@fluxo("12", "Consulta de movimentações e saldo", "RF14, RF15, RN01", "Ajustado",
       "Ajuste: validação do período e filtros por tipo e texto.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar módulo financeiro", 1, 1)
    n("d", "dec", "Escolher consulta", 1, 2)
    n("m1", "io", "Informar período, tipo e texto (opcional)", 0, 3)
    n("m2", "dec", "Data inicial ≤ data final?", 0, 4)
    n("m3", "proc", "Avisar período inválido", 1, 4)
    n("m4", "proc", "Buscar movimentações", 0, 5)
    n("m5", "io", "Exibir entradas e saídas do período", 0, 6)
    n("s1", "proc", "Somar todas as entradas registradas", 2, 3)
    n("s2", "proc", "Subtrair todas as saídas registradas", 2, 4)
    n("s3", "io", "Exibir saldo financeiro atual", 2, 5)
    n("fim", "end", "Fim", 1, 8)
    e("i", "a"); e("a", "d"); e("d", "m1", "Movimentações"); e("d", "s1", "Saldo")
    e("m1", "m2"); e("m2", "m3", "Não"); e("m3", "m1"); e("m2", "m4", "Sim"); e("m4", "m5")
    e("s1", "s2"); e("s2", "s3"); e("m5", "fim"); e("s3", "fim")


@fluxo("13", "Balanço financeiro mensal", "RF16, RN05, RN11", "Ajustado",
       "Ajuste: verifica se há movimentações antes de somar; detalha entradas por origem e forma e saídas por categoria.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar fechamento mensal", 1, 1)
    n("b", "io", "Informar mês e ano", 1, 2)
    n("d", "dec", "Há movimentações no período?", 1, 3)
    n("v", "io", "Exibir período sem movimentações", 2, 4)
    n("c", "proc", "Somar entradas por origem e forma de pagamento", 1, 4)
    n("e", "proc", "Somar saídas por categoria", 1, 5)
    n("f", "proc", "Saldo do mês = entradas − saídas", 1, 6)
    n("g", "io", "Exibir balanço com totais e detalhamento", 1, 7)
    n("fim", "end", "Fim", 1, 8)
    e("i", "a"); e("a", "b"); e("b", "d"); e("d", "v", "Não"); e("d", "c", "Sim")
    e("c", "e"); e("e", "f"); e("f", "g"); e("g", "fim"); e("v", "fim")


@fluxo("14", "Consulta da agenda de aulas", "RF05, RF20, RN10", "Mantido",
       "Mantido, mostrando também inscritos e capacidade de cada aula.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar agenda", 1, 1)
    n("b", "io", "Filtrar por dia, modalidade e sala (opcional)", 1, 2)
    n("c", "proc", "Buscar aulas ativas", 1, 3)
    n("d", "dec", "Há aulas correspondentes?", 1, 4)
    n("s", "io", "Exibir por dia: horário, aula, sala, professor e inscritos/capacidade", 0, 5)
    n("v", "io", "Informar que não há aulas correspondentes", 2, 5)
    n("fim", "end", "Fim", 1, 6)
    e("i", "a"); e("a", "b"); e("b", "c"); e("c", "d"); e("d", "s", "Sim"); e("d", "v", "Não")
    e("s", "fim"); e("v", "fim")


@fluxo("15", "Correção de lançamentos financeiros", "RF23, RF24, RNF05", "Novo",
       "Fluxo novo: editar ou excluir um lançamento digitado errado; a alteração fica na auditoria.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Consultar movimentações (fluxo 12)", 1, 1)
    n("b", "io", "Selecionar lançamento", 1, 2)
    n("d", "dec", "Editar ou excluir?", 1, 3)
    n("e1", "io", "Alterar dados no mesmo formulário do lançamento", 0, 4)
    n("e2", "dec", "Dados válidos?", 0, 5)
    n("e3", "proc", "Corrigir", 1, 5)
    n("e4", "proc", "Salvar alteração", 0, 6)
    n("x1", "io", "Pedir confirmação da exclusão", 2, 4)
    n("x2", "dec", "Exclusão confirmada?", 2, 5)
    n("x3", "proc", "Excluir lançamento", 2, 6)
    n("x4", "proc", "Manter lançamento", 3, 6)
    n("au", "proc", "Registrar a alteração na auditoria", 1, 8)
    n("r", "io", "Saldo e balanço recalculados", 1, 9)
    n("fim", "end", "Fim", 1, 10)
    e("i", "a"); e("a", "b"); e("b", "d"); e("d", "e1", "Editar"); e("d", "x1", "Excluir")
    e("e1", "e2"); e("e2", "e3", "Não"); e("e3", "e1"); e("e2", "e4", "Sim"); e("e4", "au")
    e("x1", "x2"); e("x2", "x3", "Sim"); e("x2", "x4", "Não"); e("x3", "au")
    e("au", "r"); e("r", "fim"); e("x4", "fim")


@fluxo("16", "Consulta da auditoria de acessos", "RF24, RNF03, RNF04", "Novo",
       "Fluxo novo: só a equipe vê a auditoria (IP e histórico de acesso são dados pessoais). Os registros são gravados nos fluxos 00, 05 e 15.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar Administração", 1, 1)
    n("d", "dec", "Usuário é da equipe?", 1, 2)
    n("u", "io", "Exibir apenas a lista de usuários", 2, 3)
    n("b", "proc", "Ler logs de acesso e de alterações dos últimos 30 dias", 1, 3)
    n("c", "proc", "Calcular usuários, IPs, logins e falhas", 1, 4)
    n("f", "io", "Exibir resumo, logins, logouts e alterações de dados", 1, 5)
    n("fim", "end", "Fim", 1, 6)
    e("i", "a"); e("a", "d"); e("d", "u", "Não"); e("d", "b", "Sim"); e("b", "c"); e("c", "f")
    e("f", "fim"); e("u", "fim")


@fluxo("17", "Consulta de frequência e oportunidades", "RF25, RN17, RN08, RN09", "Novo",
       "Fluxo novo: ocupação real (presentes ÷ capacidade), temperatura da aula e sugestão de promoção para o proprietário.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar Consultas", 1, 1)
    n("b", "io", "Escolher período (4, 8, 12 ou 26 semanas)", 1, 2)
    n("c", "proc", "Buscar aulas ativas e chamadas do período", 1, 3)
    n("d", "dec", "Aula tem chamada no período?", 1, 4)
    n("sd", "proc", "Marcar \u201csem dados\u201d e sugerir fazer a chamada", 3, 4)
    n("o", "proc", "Ocupação = média de presentes ÷ capacidade da sala", 1, 5)
    n("d2", "dec", "Ocupação ≥ 70%?", 1, 6)
    n("q", "proc", "Quente ou morna: sem promoção (≥ 85%: avaliar nova turma)", 0, 7)
    n("f", "proc", "Fria ou gelada: indicar promoção (< 40%: promoção forte)", 2, 7)
    n("t", "proc", "Avaliar tendência, frequência e alunos avulsos", 1, 8)
    n("r", "io", "Exibir mapa de calor, ranking, oportunidades e sugestões", 1, 9)
    n("fim", "end", "Fim", 1, 10)
    e("i", "a"); e("a", "b"); e("b", "c"); e("c", "d"); e("d", "o", "Sim"); e("d", "sd", "Não")
    e("o", "d2"); e("d2", "q", "Sim"); e("d2", "f", "Não"); e("q", "t"); e("f", "t")
    e("t", "r"); e("sd", "r"); e("r", "fim")


# ---------------------------------------------------------------------------
# Saídas
# ---------------------------------------------------------------------------
def montar(f):
    nos = list(f["nos"].values())
    arestas = []
    contador = {}
    for a, b, rotulo, via in f["arestas"]:
        s, d = f["nos"][a], f["nos"][b]
        chave = via or ("lane" if (d.row < s.row and s.col == d.col) else None)
        idx = contador.get(chave, 0) if chave else 0
        if chave:
            contador[chave] = idx + 1
        ps, pd, pts = rotear(s, d, via, nos, idx)
        arestas.append({"s": s, "d": d, "rotulo": rotulo, "ps": ps, "pd": pd, "pts": pts})
    xs = [n.left for n in nos] + [n.right for n in nos] + [p[0] for e in arestas for p in e["pts"]]
    ys = [n.bottom for n in nos] + [p[1] for e in arestas for p in e["pts"]]
    largura = max(max(xs) + 50, 760)
    minx = min(min(xs) - 30, 0)
    altura = max(ys) + 110
    return nos, arestas, minx, largura, altura


def svg_fluxo(f):
    nos, arestas, minx, largura, altura = montar(f)
    w = largura - minx
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{altura:.0f}" '
           f'viewBox="{minx:.0f} 0 {w:.0f} {altura:.0f}" font-family="Liberation Sans, Arial, sans-serif">',
           f'<rect x="{minx:.0f}" y="0" width="{w:.0f}" height="{altura:.0f}" fill="{FUNDO}"/>']
    t = html.escape
    out.append(f'<text x="{minx + 36:.0f}" y="46" font-size="22" font-weight="bold" fill="{TINTA}">'
               f'Fluxo {f["numero"]} — {t(f["titulo"])}</text>')
    out.append(f'<text x="{minx + 36:.0f}" y="72" font-size="12.5" fill="#5a5768">Requisitos: '
               f'{t(f["requisitos"])}   ·   Situação: {t(f["situacao"])}</text>')
    for e in arestas:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in e["pts"])
        out.append(f'<polyline points="{pts}" fill="none" stroke="{LINHA}" stroke-width="1.4"/>')
        (x1, y1), (x2, y2) = e["pts"][-2], e["pts"][-1]
        if abs(x2 - x1) > abs(y2 - y1):
            s = 1 if x2 > x1 else -1
            tri = [(x2, y2), (x2 - s * 9, y2 - 4.5), (x2 - s * 9, y2 + 4.5)]
        else:
            s = 1 if y2 > y1 else -1
            tri = [(x2, y2), (x2 - 4.5, y2 - s * 9), (x2 + 4.5, y2 - s * 9)]
        out.append('<polygon points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in tri)
                   + f'" fill="{LINHA}"/>')
    for n in nos:
        fill, stroke = CORES[n.kind]
        if n.kind in ("start", "end"):
            out.append(f'<ellipse cx="{n.cx}" cy="{n.cy}" rx="{n.w/2}" ry="{n.h/2}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        elif n.kind == "proc":
            out.append(f'<rect x="{n.left}" y="{n.top}" width="{n.w}" height="{n.h}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        elif n.kind == "io":
            p = [(n.left + SKEW, n.top), (n.right, n.top), (n.right - SKEW, n.bottom), (n.left, n.bottom)]
            out.append('<polygon points="' + " ".join(f"{x},{y}" for x, y in p)
                       + f'" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        else:
            p = [(n.cx, n.top), (n.right, n.cy), (n.cx, n.bottom), (n.left, n.cy)]
            out.append('<polygon points="' + " ".join(f"{x},{y}" for x, y in p)
                       + f'" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        linhas = wrap(n.text, WRAP[n.kind])
        y = n.cy - (len(linhas) - 1) * (FONT + 2) / 2 + FONT * 0.35
        peso = ' font-weight="bold"' if n.kind in ("start", "end", "dec") else ""
        for i, linha in enumerate(linhas):
            out.append(f'<text x="{n.cx}" y="{y + i * (FONT + 2):.1f}" font-size="{FONT}" '
                       f'text-anchor="middle" fill="{TINTA}"{peso}>{t(linha)}</text>')
    for e in arestas:
        if not e["rotulo"]:
            continue
        x, y, anc = posicao_rotulo(e["pts"])
        larg = len(e["rotulo"]) * 6.2 + 6
        rx = x - larg / 2 if anc == "middle" else x - 3
        out.append(f'<rect x="{rx:.1f}" y="{y - 11:.1f}" width="{larg:.1f}" height="14" fill="{FUNDO}"/>')
        out.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="11" text-anchor="{anc}" '
                   f'fill="#3a3850" font-style="italic">{t(e["rotulo"])}</text>')
    # nota de mudanças
    linhas = wrap("O que mudou: " + f["mudancas"], int((w - 72) / 6.4))
    y0 = altura - 22 - (len(linhas) - 1) * 15
    for i, linha in enumerate(linhas):
        out.append(f'<text x="{minx + 36:.0f}" y="{y0 + i * 15:.0f}" font-size="11.5" fill="#5a5768">{t(linha)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def svg_indice():
    t = html.escape
    linhas_y = 150
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="800" viewBox="0 0 1000 800" '
           'font-family="Liberation Sans, Arial, sans-serif">', '<rect width="1000" height="800" fill="#ffffff"/>',
           f'<text x="50" y="62" font-size="28" font-weight="bold" fill="{TINTA}">Portal da Dança — Fluxogramas</text>',
           '<text x="50" y="92" font-size="14" fill="#5a5768">Versão 1.0 · 10/11/2026 · revisada conforme as observações da professora e o sistema implementado</text>',
           f'<text x="50" y="{linhas_y - 12}" font-size="12" font-weight="bold" fill="#5a5768">Nº</text>',
           f'<text x="100" y="{linhas_y - 12}" font-size="12" font-weight="bold" fill="#5a5768">FLUXO</text>',
           f'<text x="520" y="{linhas_y - 12}" font-size="12" font-weight="bold" fill="#5a5768">REQUISITOS</text>',
           f'<text x="860" y="{linhas_y - 12}" font-size="12" font-weight="bold" fill="#5a5768">SITUAÇÃO</text>']
    cores = {"Novo": "#2f7a55", "Corrigido": "#a8461a", "Ajustado": "#a8761a", "Mantido": "#5a5768"}
    for i, f in enumerate(FLUXOS):
        y = linhas_y + 10 + i * 33
        if i % 2 == 0:
            out.append(f'<rect x="40" y="{y - 21}" width="920" height="33" fill="#f4f3f8"/>')
        out.append(f'<text x="50" y="{y}" font-size="14" font-weight="bold" fill="{TINTA}">{f["numero"]}</text>')
        out.append(f'<text x="100" y="{y}" font-size="14" fill="{TINTA}">{t(f["titulo"])}</text>')
        out.append(f'<text x="520" y="{y}" font-size="12" fill="#5a5768">{t(f["requisitos"])}</text>')
        out.append(f'<text x="860" y="{y}" font-size="13" font-weight="bold" fill="{cores[f["situacao"]]}">{f["situacao"]}</text>')
    out.append('<text x="50" y="780" font-size="12" fill="#5a5768">Legenda: elipse = início/fim · retângulo = processo · '
               'paralelogramo = entrada/saída de dados · losango = decisão.</text>')
    out.append("</svg>")
    return "\n".join(out)


def drawio():
    t = lambda s: html.escape(s, quote=True)
    estilos = {
        "start": "ellipse;whiteSpace=wrap;html=1;fontStyle=1;",
        "end": "ellipse;whiteSpace=wrap;html=1;fontStyle=1;",
        "proc": "rounded=0;whiteSpace=wrap;html=1;",
        "io": "shape=parallelogram;perimeter=parallelogramPerimeter;whiteSpace=wrap;html=1;fixedSize=1;size=16;",
        "dec": "rhombus;whiteSpace=wrap;html=1;fontStyle=1;",
    }
    paginas = []
    for pid, f in enumerate(FLUXOS):
        nos, arestas, minx, largura, altura = montar(f)
        cel = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>',
               f'<mxCell id="titulo" value="{t("Fluxo " + f["numero"] + " — " + f["titulo"])}" '
               'style="text;html=1;fontSize=20;fontStyle=1;align=left;verticalAlign=middle;" vertex="1" parent="1">'
               f'<mxGeometry x="{minx + 36:.0f}" y="24" width="900" height="30" as="geometry"/></mxCell>',
               f'<mxCell id="req" value="{t("Requisitos: " + f["requisitos"] + "  ·  Situação: " + f["situacao"])}" '
               'style="text;html=1;fontSize=12;fontColor=#5a5768;align=left;verticalAlign=middle;" vertex="1" parent="1">'
               f'<mxGeometry x="{minx + 36:.0f}" y="56" width="900" height="22" as="geometry"/></mxCell>',
               f'<mxCell id="nota" value="{t("O que mudou: " + f["mudancas"])}" '
               'style="text;html=1;fontSize=11;fontColor=#5a5768;align=left;verticalAlign=top;whiteSpace=wrap;" vertex="1" parent="1">'
               f'<mxGeometry x="{minx + 36:.0f}" y="{altura - 60:.0f}" width="{largura - minx - 72:.0f}" height="50" as="geometry"/></mxCell>']
        for n in nos:
            fill, stroke = CORES[n.kind]
            cel.append(f'<mxCell id="{n.id}" value="{t(n.text)}" style="{estilos[n.kind]}fillColor={fill};'
                       f'strokeColor={stroke};fontSize=11;" vertex="1" parent="1">'
                       f'<mxGeometry x="{n.left:.0f}" y="{n.top:.0f}" width="{n.w}" height="{n.h}" as="geometry"/></mxCell>')
        for i, e in enumerate(arestas):
            ex, ey = REL[e["ps"]]
            nx, ny = REL[e["pd"]]
            pts = "".join(f'<mxPoint x="{x:.0f}" y="{y:.0f}"/>' for x, y in e["pts"][1:-1])
            cel.append(f'<mxCell id="e{i}" value="{t(e["rotulo"])}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;'
                       f'html=1;endArrow=block;endFill=1;strokeColor={LINHA};fontSize=11;fontStyle=2;'
                       f'exitX={ex};exitY={ey};exitDx=0;exitDy=0;entryX={nx};entryY={ny};entryDx=0;entryDy=0;" '
                       f'edge="1" parent="1" source="{e["s"].id}" target="{e["d"].id}">'
                       f'<mxGeometry relative="1" as="geometry"><Array as="points">{pts}</Array></mxGeometry></mxCell>')
        nome = f'{f["numero"]} - {f["titulo"]}'
        paginas.append(f'<diagram id="fluxo{f["numero"]}" name="{t(nome)}"><mxGraphModel dx="1200" dy="900" '
                       f'grid="1" gridSize="10" guides="1" page="1" pageScale="1" pageWidth="{largura - minx:.0f}" '
                       f'pageHeight="{altura:.0f}" math="0" shadow="0"><root>{"".join(cel)}</root></mxGraphModel></diagram>')
    return ('<mxfile host="gerar_fluxogramas.py" version="24.0.0">' + "".join(paginas) + "</mxfile>")


def main():
    svg_dir = PASTA / "svg"
    svg_dir.mkdir(exist_ok=True)
    arquivos = [svg_dir / "00_indice.svg"]
    arquivos[0].write_text(svg_indice(), encoding="utf-8")
    for f in FLUXOS:
        p = svg_dir / f'{f["numero"]}.svg'
        p.write_text(svg_fluxo(f), encoding="utf-8")
        arquivos.append(p)
    (PASTA / "Portal_da_Danca_Fluxogramas_v1.0.drawio").write_text(drawio(), encoding="utf-8")
    # Lista usada pelo relatório para montar a rastreabilidade (requisito → fluxos)
    (PASTA / "fluxos.json").write_text(json.dumps([
        {"numero": f["numero"], "titulo": f["titulo"], "situacao": f["situacao"],
         "requisitos": [r.strip() for r in f["requisitos"].split(",")], "mudancas": f["mudancas"]}
        for f in FLUXOS], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(FLUXOS)} fluxos → drawio e {len(arquivos)} SVGs")

    soffice, pdfunite = shutil.which("soffice"), shutil.which("pdfunite")
    if not (soffice and pdfunite):
        print("LibreOffice ou pdfunite ausente: PDF não gerado.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf:draw_pdf_Export", "--outdir", tmp,
                        *map(str, arquivos)], check=True, capture_output=True)
        pdfs = [str(Path(tmp) / (a.stem + ".pdf")) for a in arquivos]
        destino = PASTA / "Portal_da_Danca_Fluxogramas_v1.0.pdf"
        subprocess.run([pdfunite, *pdfs, str(destino)], check=True)
    print(f"PDF: {destino}")


if __name__ == "__main__":
    sys.exit(main())
