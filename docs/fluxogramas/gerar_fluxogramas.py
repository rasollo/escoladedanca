"""Gera os fluxogramas do Portal da Dança (versão 2.0).

Uma única descrição de cada fluxo produz:
  * Portal_da_Danca_Fluxogramas_v2.0.drawio  — uma aba por fluxo, editável no draw.io
  * svg/NN.svg                             — desenho de cada fluxo
  * Portal_da_Danca_Fluxogramas_v2.0.pdf     — via LibreOffice + pdfunite (se disponíveis)

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


@fluxo("00", "Acesso ao sistema", "RF22, RF24, RF25, RF31, RF37, RNF03, RN17", "Atualizado",
       "v2.0: conta bloqueada não entra; troca de senha obrigatória no primeiro acesso (RF37); escolha do ambiente quando a conta tem vários papéis (RF31); cada página é negada por padrão e liberada só ao papel ativo (RF25, RN17). Mantidos o login obrigatório e os registros de login, falha, acesso e logout.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar uma página do sistema", 1, 1)
    n("d1", "dec", "Usuário já autenticado?", 1, 2)
    n("u", "io", "Informar usuário e senha", 2, 3)
    n("d2", "dec", "Senha válida e conta ativa?", 2, 4)
    n("f", "proc", "Registrar LOGIN_FALHOU e exibir aviso", 3, 4)
    n("ok", "proc", "Registrar LOGIN_OK (usuário e IP)", 2, 5)
    n("d3", "dec", "Troca de senha pendente (1º acesso)?", 1, 6)
    n("ts", "io", "Trocar a senha provisória (demais páginas bloqueadas)", 2, 7)
    n("d4", "dec", "Conta tem mais de um papel?", 1, 8)
    n("amb", "io", "Escolher o ambiente (papel ativo da sessão)", 2, 9)
    n("d5", "dec", "Papel ativo pode ver a página?", 1, 10)
    n("neg", "io", "Exibir acesso negado (403)", 2, 11)
    n("p", "io", "Exibir página solicitada", 1, 11)
    n("r", "proc", "Registrar acesso (usuário, IP, página)", 1, 12)
    n("d6", "dec", "Clicou em Sair?", 1, 13)
    n("lo", "proc", "Registrar LOGOUT e encerrar sessão", 1, 14)
    n("fim", "end", "Fim", 1, 15)
    e("i", "a"); e("a", "d1"); e("d1", "d3", "Sim"); e("d1", "u", "Não"); e("u", "d2")
    e("d2", "f", "Não"); e("f", "u"); e("d2", "ok", "Sim"); e("ok", "d3")
    e("d3", "ts", "Sim"); e("d3", "d4", "Não"); e("ts", "d4")
    e("d4", "amb", "Sim"); e("d4", "d5", "Não"); e("amb", "d5")
    e("d5", "p", "Sim"); e("d5", "neg", "Não"); e("neg", "fim"); e("p", "r")
    e("r", "d6"); e("d6", "a", "Não", "L"); e("d6", "lo", "Sim"); e("lo", "fim")


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


@fluxo("04", "Agendamento de aulas", "RF19, RF20, RF36, RN09, RN10, RN13, RN14, RN15, RN17", "Atualizado",
       "v2.0: a aula pode acontecer em vários dias da semana no mesmo horário, com vigência opcional (RF36); os conflitos de sala e professor são verificados em todos os dias escolhidos; o professor só agenda e altera as próprias aulas, e desativar ou remover é exclusivo do Administrativo (RN17).")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar agenda de aulas", 1, 1)
    n("d", "dec", "Nova aula ou aula existente?", 1, 2)
    n("nv", "proc", "Iniciar novo agendamento (professor: aula fica em seu nome)", 0, 3)
    n("ex", "io", "Selecionar aula existente (professor: só as próprias)", 2, 3)
    n("op", "dec", "Alterar, desativar ou remover?", 2, 4)
    n("dados", "io", "Informar modalidade, dias da semana, horário, sala, professor, mensalidade e vigência", 1, 4)
    n("v1", "dec", "Entre 18h e 22h, término após o início e vigência coerente?", 1, 5)
    n("v2", "dec", "Sala e professor livres em todos os dias escolhidos?", 1, 6)
    n("v3", "dec", "Inscritos cabem na sala (até 40)?", 1, 7)
    n("rev", "proc", "Revisar dados ou organizar outra turma", 0, 6)
    n("sv", "proc", "Salvar agendamento", 1, 8)
    n("ag", "io", "Aula disponível na agenda em cada dia escolhido", 1, 9)
    n("des", "proc", "Desativar aula e encerrar as matrículas (só Administrativo)", 2, 5)
    n("rm", "dec", "Aula tem presenças ou matrículas?", 3, 5)
    n("rm1", "io", "Orientar a desativar (histórico protegido)", 3, 6)
    n("rm2", "proc", "Remover aula (só Administrativo)", 4, 6)
    n("fim", "end", "Fim", 1, 10)
    e("i", "a"); e("a", "d"); e("d", "nv", "Nova"); e("d", "ex", "Existente")
    e("nv", "dados"); e("ex", "op"); e("op", "dados", "Alterar")
    e("op", "des", "Desativar"); e("op", "rm", "Remover")
    e("dados", "v1"); e("v1", "rev", "Não"); e("v1", "v2", "Sim"); e("v2", "rev", "Não")
    e("v2", "v3", "Sim"); e("v3", "rev", "Não"); e("v3", "sv", "Sim"); e("rev", "dados", "", "L")
    e("sv", "ag"); e("ag", "fim")
    e("rm", "rm1", "Sim"); e("rm", "rm2", "Não")
    e("des", "fim"); e("rm1", "fim"); e("rm2", "fim")


@fluxo("05", "Matrícula de alunos nas aulas", "RF20, RF21, RF24, RF32, RN07, RN08, RN09, RN18, RN20", "Atualizado",
       "v2.0: a matrícula copia a mensalidade da aula e aceita desconto percentual ou fixo (RN18); o Administrativo pode suspender ou cancelar com motivo e reativar a suspensa, respeitando a lotação (RF32, RN20). Matrículas encerradas não geram novas cobranças, mas contam no salário do mês em que estiveram ativas.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("d0", "dec", "Vincular alunos ou gerenciar uma matrícula?", 1, 1)
    n("a", "io", "Selecionar aula agendada (professor: só as próprias)", 1, 2)
    n("b", "io", "Exibir inscritos, capacidade da sala e vagas", 1, 3)
    n("c", "io", "Marcar alunos a inscrever e desmarcar os que saíram", 1, 4)
    n("d", "dec", "Total de inscritos ≤ capacidade da sala?", 1, 5)
    n("r", "proc", "Revisar seleção ou organizar outra turma", 0, 5)
    n("m1", "proc", "Abrir matrícula (início = hoje, mensalidade da aula)", 1, 6)
    n("m2", "proc", "Encerrar matrícula (fim = hoje) dos desmarcados", 1, 7)
    n("au", "proc", "Registrar a alteração na auditoria", 1, 8)
    n("s", "io", "Matrículas usadas nas cobranças (fluxo 10) e no salário (fluxo 11)", 1, 9)
    n("g", "io", "Abrir a matrícula no cadastro do aluno (Administrativo)", 3, 2)
    n("g2", "dec", "Qual ação?", 3, 3)
    n("ed", "io", "Ajustar mensalidade e desconto (% ou valor fixo)", 2, 4)
    n("en", "io", "Escolher suspender ou cancelar e informar o motivo", 3, 4)
    n("en2", "proc", "Encerrar a matrícula (fim = hoje), sem novas cobranças", 3, 5)
    n("re", "proc", "Conferir se está suspensa, se a aula está ativa e se há vaga", 4, 4)
    n("re2", "proc", "Nova matrícula (início = hoje) com a mesma mensalidade", 4, 5)
    n("fim", "end", "Fim", 1, 10)
    e("i", "d0"); e("d0", "a", "Vincular"); e("d0", "g", "Gerenciar")
    e("a", "b"); e("b", "c"); e("c", "d"); e("d", "r", "Não"); e("r", "c")
    e("d", "m1", "Sim"); e("m1", "m2"); e("m2", "au"); e("au", "s"); e("s", "fim")
    e("g", "g2"); e("g2", "ed", "Ajustar valor"); e("g2", "en", "Encerrar"); e("g2", "re", "Reativar")
    e("en", "en2"); e("re", "re2"); e("ed", "fim"); e("en2", "fim"); e("re2", "fim")


@fluxo("06", "Registro de presença e faltas", "RF03, RF04, RF21, RF33, RN08, RN19", "Atualizado",
       "v2.0: a chamada de cada aula e data fica aberta, concluída ou cancelada (RF33). O professor registra e conclui a chamada das próprias aulas; uma chamada concluída só é corrigida pela administração, com motivo; a aula só é cancelada sem registros e com motivo (RN19). Mantidos os avulsos, o dia da aula e a capacidade.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "io", "Selecionar aula e data (professor: só as próprias)", 1, 1)
    n("d1", "dec", "A aula acontece nessa data (dia e vigência)?", 1, 2)
    n("x", "proc", "Informar o dia correto da aula", 2, 2)
    n("st", "dec", "Situação da chamada?", 1, 3)
    n("ca", "io", "Exibir aula cancelada e o motivo", 0, 4)
    n("co", "dec", "Usuário é da administração?", 2, 4)
    n("mo", "io", "Informar o motivo da correção", 2, 5)
    n("vi", "io", "Somente consultar a chamada concluída", 3, 5)
    n("b", "io", "Exibir inscritos e avulsos já registrados", 1, 4)
    n("ac", "dec", "Cancelar a aula nesta data?", 1, 5)
    n("cs", "proc", "Cancelar com motivo (só sem registros)", 0, 6)
    n("c", "io", "Marcar presente ou falta para cada aluno", 1, 6)
    n("d2", "dec", "Há alunos avulsos (sem matrícula)?", 1, 7)
    n("av", "io", "Adicionar um ou mais avulsos ou retirar um incluído por engano", 2, 8)
    n("d3", "dec", "Presentes ≤ capacidade da sala?", 1, 9)
    n("rv", "proc", "Revisar marcações", 2, 9)
    n("s", "proc", "Salvar registros da aula (um por aluno e data)", 1, 10)
    n("cc", "dec", "Concluir a chamada?", 1, 11)
    n("ab", "proc", "Chamada continua aberta", 2, 12)
    n("cn", "proc", "Chamada concluída (correção: motivo registrado)", 1, 12)
    n("fim", "end", "Fim", 1, 13)
    e("i", "a"); e("a", "d1"); e("d1", "x", "Não"); e("x", "a"); e("d1", "st", "Sim")
    e("st", "ca", "Cancelada"); e("st", "co", "Concluída"); e("st", "b", "Aberta")
    e("co", "mo", "Sim"); e("co", "vi", "Não"); e("mo", "c")
    e("b", "ac"); e("ac", "cs", "Sim"); e("ac", "c", "Não")
    e("c", "d2"); e("d2", "av", "Sim"); e("d2", "d3", "Não"); e("av", "d3")
    e("d3", "rv", "Não"); e("rv", "c", "", "R"); e("d3", "s", "Sim"); e("s", "cc")
    e("cc", "cn", "Sim"); e("cc", "ab", "Não"); e("cn", "fim"); e("ab", "fim")
    e("ca", "fim", "", "L"); e("cs", "fim"); e("vi", "fim")


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


@fluxo("10", "Cobranças de mensalidade", "RF10, RF11, RF23, RF34, RN02, RN04, RN06, RN08, RN12, RN18, RN20", "Atualizado",
       "v2.0: a mensalidade passou a ser uma cobrança mensal por matrícula ativa (mensalidade − desconto, vencimento no dia 5), que não altera o caixa. O recebimento pode ser parcial, até o saldo devedor, e entra como entrada; a correção é por estorno com motivo (saída vinculada); a cobrança só é cancelada sem recebimentos. A situação (pendente, parcial, atrasada ou paga) segue informativa (RN08).")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar mensalidades", 1, 1)
    n("b", "io", "Escolher mês ou período e situação; exibir cobranças, totais e contagem por situação", 1, 2)
    n("d", "dec", "Qual operação?", 1, 3)
    n("g1", "proc", "Gerar 1 cobrança por matrícula ativa sem cobrança no mês (o caixa não muda)", 0, 4)
    n("x", "io", "Exportar CSV com os filtros escolhidos", 2, 4)
    n("c", "io", "Abrir a cobrança do aluno", 1, 4)
    n("c2", "dec", "Receber, estornar ou cancelar?", 1, 5)
    n("e1", "io", "Selecionar recebimento e informar o motivo do estorno", 0, 6)
    n("e2", "proc", "Registrar saída de estorno vinculada ao recebimento", 0, 7)
    n("r1", "io", "Informar valor, data e forma de pagamento", 1, 6)
    n("r2", "dec", "0 < valor ≤ saldo devedor?", 1, 7)
    n("r3", "proc", "Corrigir o valor", 2, 7)
    n("r4", "proc", "Registrar entrada (origem = mensalidade) vinculada à cobrança", 1, 8)
    n("r5", "proc", "Atualizar saldo e situação: pendente, parcial, atrasada ou paga", 1, 9)
    n("k1", "dec", "Cobrança tem recebimentos ativos?", 3, 6)
    n("k2", "io", "Orientar a estornar antes de cancelar", 4, 7)
    n("k3", "proc", "Cancelar a cobrança com motivo", 3, 7)
    n("fim", "end", "Fim", 1, 10)
    e("i", "a"); e("a", "b"); e("b", "d")
    e("d", "g1", "Gerar"); e("d", "c", "Abrir cobrança"); e("d", "x", "Exportar")
    e("g1", "fim", "", "L"); e("x", "fim", "", "R")
    e("c", "c2"); e("c2", "e1", "Estornar"); e("c2", "r1", "Receber"); e("c2", "k1", "Cancelar")
    e("e1", "e2"); e("e2", "r5")
    e("r1", "r2"); e("r2", "r3", "Não"); e("r3", "r1"); e("r2", "r4", "Sim"); e("r4", "r5"); e("r5", "fim")
    e("k1", "k3", "Não"); e("k1", "k2", "Sim"); e("k3", "fim"); e("k2", "fim")


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


@fluxo("17", "Consulta de frequência e oportunidades", "RF27, RN08, RN09, RN17", "Atualizado",
       "Fluxo novo: ocupação real (presentes ÷ capacidade), temperatura da aula e sugestão de promoção para o proprietário. v2.0: requisito corrigido para RF27 (o RF25 passou a ser o controle de acesso).")
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


@fluxo("18", "Comunicados por aula", "RF28, RN17", "Novo",
       "Fluxo novo (v2.0): o Administrativo publica em qualquer aula ativa e o professor só nas próprias; o aluno vê apenas os comunicados das aulas em que está matriculado.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar Comunicados", 1, 1)
    n("d", "dec", "Papel ativo?", 1, 2)
    n("p1", "io", "Escolher a aula (professor: só as próprias) e escrever título e mensagem", 0, 3)
    n("p2", "dec", "Aula permitida e campos preenchidos?", 0, 4)
    n("p3", "proc", "Exibir erro e corrigir", 1, 4)
    n("p4", "proc", "Publicar o comunicado com autor e data", 0, 5)
    n("p5", "io", "Comunicado visível aos alunos matriculados na aula", 0, 6)
    n("al1", "proc", "Buscar comunicados das aulas em que o aluno está matriculado", 2, 3)
    n("al2", "io", "Exibir comunicados, do mais recente ao mais antigo", 2, 4)
    n("fim", "end", "Fim", 1, 7)
    e("i", "a"); e("a", "d"); e("d", "p1", "Administrativo / Professor"); e("d", "al1", "Aluno")
    e("p1", "p2"); e("p2", "p3", "Não"); e("p3", "p1"); e("p2", "p4", "Sim"); e("p4", "p5"); e("p5", "fim")
    e("al1", "al2"); e("al2", "fim")


@fluxo("19", "Solicitações dos alunos", "RF29, RN17", "Novo",
       "Fluxo novo (v2.0): o aluno registra o pedido e acompanha a resposta; o Administrativo muda a situação e responde. Concluir ou recusar exige resposta, e nenhum dado é alterado automaticamente.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar Solicitações", 1, 1)
    n("d", "dec", "Papel ativo?", 1, 2)
    n("s1", "io", "Escolher o tipo (cadastro, frequência, matrícula ou mensalidade) e descrever", 0, 3)
    n("s2", "dec", "Descrição informada?", 0, 4)
    n("s3", "proc", "Pedir a descrição", 1, 4)
    n("s4", "proc", "Registrar a solicitação como pendente", 0, 5)
    n("s5", "io", "Acompanhar a situação e a resposta", 0, 6)
    n("r1", "io", "Filtrar por situação e abrir a solicitação", 2, 3)
    n("r2", "io", "Escolher a situação (em análise, concluída ou recusada) e responder", 2, 4)
    n("r3", "dec", "Concluída ou recusada sem resposta?", 2, 5)
    n("r4", "proc", "Exigir a resposta", 3, 5)
    n("r5", "proc", "Salvar situação e resposta (sem alterar outros dados)", 2, 6)
    n("r6", "io", "Aluno vê a resposta em Solicitações", 2, 7)
    n("fim", "end", "Fim", 1, 8)
    e("i", "a"); e("a", "d"); e("d", "s1", "Aluno"); e("d", "r1", "Administrativo")
    e("s1", "s2"); e("s2", "s3", "Não"); e("s3", "s1"); e("s2", "s4", "Sim"); e("s4", "s5"); e("s5", "fim")
    e("r1", "r2"); e("r2", "r3"); e("r3", "r4", "Sim"); e("r4", "r2"); e("r3", "r5", "Não")
    e("r5", "r6"); e("r6", "fim")


@fluxo("20", "Relatórios do período", "RF34, RN08, RN18", "Novo",
       "Fluxo novo (v2.0): indicadores do período e quadro de mensalidades; cada situação abre a lista de mensalidades já filtrada, e os dados podem ser exportados em CSV.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar Relatórios (Administrativo)", 1, 1)
    n("b", "io", "Informar o período (de/até) ou usar um atalho", 1, 2)
    n("d1", "dec", "Data inicial ≤ data final?", 1, 3)
    n("x", "proc", "Avisar período inválido", 2, 3)
    n("c", "proc", "Calcular frequência, chamadas, matrículas encerradas, entradas e saídas", 1, 4)
    n("m", "proc", "Calcular mensalidades: previsto, recebido, em aberto, saldo vencido e quantidade por situação", 1, 5)
    n("r", "io", "Exibir indicadores e quadro de mensalidades", 1, 6)
    n("d2", "dec", "Próxima ação?", 1, 7)
    n("l", "io", "Abrir a lista de mensalidades do período na situação clicada", 0, 8)
    n("ex", "io", "Baixar CSV de presenças, mensalidades ou movimentações", 2, 8)
    n("fim", "end", "Fim", 1, 9)
    e("i", "a"); e("a", "b"); e("b", "d1"); e("d1", "x", "Não"); e("x", "b"); e("d1", "c", "Sim")
    e("c", "m"); e("m", "r"); e("r", "d2")
    e("d2", "l", "Clicar numa situação"); e("d2", "ex", "Exportar"); e("d2", "fim", "Concluir")
    e("l", "fim"); e("ex", "fim")


@fluxo("21", "Backup e restauração dos dados", "RF35, RF24, RNF04", "Novo",
       "Fluxo novo (v2.0): só o superusuário exporta e restaura. A restauração exige digitar RESTAURAR, valida o arquivo e roda em transação única: qualquer erro desfaz tudo. As duas operações ficam na auditoria.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar Acessos (Administração)", 1, 1)
    n("d", "dec", "Usuário é superusuário?", 1, 2)
    n("n", "io", "Exibir acesso negado", 3, 3)
    n("o", "dec", "Exportar ou restaurar?", 1, 3)
    n("e1", "proc", "Gerar arquivo JSON com todos os dados", 0, 4)
    n("e2", "proc", "Registrar BACKUP_EXPORTADO na auditoria", 0, 5)
    n("e3", "io", "Baixar o arquivo (contém dados pessoais: guardar com cuidado)", 0, 6)
    n("r1", "io", "Enviar o arquivo .json e digitar RESTAURAR", 1, 4)
    n("r2", "dec", "Confirmação e arquivo válidos (até 50 MB)?", 1, 5)
    n("r4", "proc", "Substituir os dados em transação única", 1, 6)
    n("r5", "dec", "Restauração concluída sem erro?", 1, 7)
    n("r3", "io", "Exibir o erro; nenhum dado é alterado", 2, 7)
    n("r7", "proc", "Registrar BACKUP_RESTAURADO e encerrar a sessão", 1, 8)
    n("r8", "io", "Entrar novamente", 1, 9)
    n("fim", "end", "Fim", 1, 10)
    e("i", "a"); e("a", "d"); e("d", "n", "Não"); e("d", "o", "Sim"); e("n", "fim")
    e("o", "e1", "Exportar"); e("o", "r1", "Restaurar"); e("e1", "e2"); e("e2", "e3"); e("e3", "fim")
    e("r1", "r2"); e("r2", "r3", "Não"); e("r2", "r4", "Sim"); e("r4", "r5")
    e("r5", "r3", "Não"); e("r5", "r7", "Sim"); e("r7", "r8"); e("r8", "fim"); e("r3", "fim")


@fluxo("22", "Aniversariantes do mês", "RF26, RNF04, RN17", "Novo",
       "Fluxo novo (v2.0): lista alunos e professores ativos que fazem aniversário no mês. O ano de nascimento nunca é exibido; a idade a completar aparece só para o Administrativo e o Professor.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar Aniversariantes", 1, 1)
    n("b", "io", "Escolher o mês (padrão: mês atual)", 1, 2)
    n("c", "proc", "Buscar alunos e professores ativos nascidos nesse mês", 1, 3)
    n("d", "dec", "Há aniversariantes?", 1, 4)
    n("v", "io", "Informar que não há aniversariantes", 3, 5)
    n("o", "proc", "Ordenar por dia e destacar o aniversário de hoje", 1, 5)
    n("p", "dec", "Papel é Administrativo ou Professor?", 1, 6)
    n("id", "io", "Exibir dia, nome e idade a completar", 0, 7)
    n("si", "io", "Exibir dia e nome, sem a idade", 2, 7)
    n("fim", "end", "Fim", 1, 8)
    e("i", "a"); e("a", "b"); e("b", "c"); e("c", "d"); e("d", "v", "Não"); e("d", "o", "Sim")
    e("o", "p"); e("p", "id", "Sim"); e("p", "si", "Não"); e("id", "fim"); e("si", "fim"); e("v", "fim")


@fluxo("23", "Alunos do professor", "RF38, RN17", "Novo",
       "Fluxo novo (v2.0): o professor vê só os alunos matriculados nas próprias aulas, com contato e frequência nessas aulas.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "proc", "Acessar Meus alunos (Professor)", 1, 1)
    n("d", "dec", "Usuário vinculado a um professor ativo?", 1, 2)
    n("n", "io", "Exibir acesso negado (vincular em Acessos)", 3, 3)
    n("b", "proc", "Buscar matrículas ativas nas aulas do professor", 1, 3)
    n("c", "proc", "Calcular a frequência de cada aluno nessas aulas", 1, 4)
    n("d2", "dec", "Há alunos matriculados?", 1, 5)
    n("v", "io", "Informar que não há alunos", 2, 6)
    n("s", "io", "Exibir aluno, contato, aulas e frequência", 1, 6)
    n("fim", "end", "Fim", 1, 7)
    e("i", "a"); e("a", "d"); e("d", "n", "Não"); e("d", "b", "Sim"); e("n", "fim")
    e("b", "c"); e("c", "d2"); e("d2", "v", "Não"); e("d2", "s", "Sim"); e("s", "fim"); e("v", "fim")


@fluxo("24", "Criação dos usuários padrão", "RF39, RF25, RF37, RN17", "Novo",
       "Fluxo novo (v2.0): comando de terminal que cria o responsavel (Administrativo) e um acesso de professor e um de aluno ligados a cadastros existentes. Não apaga nem duplica dados e pode rodar de novo.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "io", "Rodar portal.py usuarios (opções: --senha, --trocar-senha)", 1, 1)
    n("b", "dec", "Senha informada?", 1, 2)
    n("g", "proc", "Gerar senha aleatória (exibida uma vez)", 2, 3)
    n("v", "proc", "Validar senha forte (aviso se fraca)", 1, 3)
    n("c", "dec", "Usuário responsavel já existe?", 1, 4)
    n("cr", "proc", "Criar responsavel (Administrativo, superusuário)", 0, 5)
    n("ma", "proc", "Manter (senha só muda com --redefinir)", 1, 5)
    n("p", "proc", "Para Professor e Aluno: escolher o cadastro ativo (ou o informado)", 1, 6)
    n("d2", "dec", "Cadastro já tem acesso?", 1, 7)
    n("k", "io", "Manter o acesso existente", 2, 8)
    n("cu", "proc", "Criar usuário com o papel, vincular ao cadastro e marcar troca de senha se pedido", 1, 8)
    n("r", "io", "Exibir login, papel, cadastro e situação de cada usuário", 1, 9)
    n("fim", "end", "Fim", 1, 10)
    e("i", "a"); e("a", "b"); e("b", "g", "Não"); e("b", "v", "Sim"); e("g", "c"); e("v", "c")
    e("c", "cr", "Não"); e("c", "ma", "Sim"); e("cr", "p"); e("ma", "p"); e("p", "d2")
    e("d2", "k", "Sim"); e("d2", "cu", "Não"); e("k", "r"); e("cu", "r"); e("r", "fim")


@fluxo("25", "Preferências da conta", "RF30, RF37", "Novo",
       "Fluxo novo (v2.0): qualquer usuário troca a própria senha (senha atual e regras de senha forte) e alterna o tema claro/escuro, guardado no navegador.")
def _(n, e):
    n("i", "start", "Início", 1, 0)
    n("a", "dec", "Alterar senha ou tema?", 1, 1)
    n("t1", "proc", "Alternar tema claro/escuro (guardado neste navegador)", 0, 2)
    n("s1", "io", "Informar senha atual, nova senha e confirmação", 1, 2)
    n("s2", "dec", "Senha atual correta?", 1, 3)
    n("s3", "dec", "Nova senha forte e confirmação igual?", 1, 4)
    n("er", "proc", "Exibir erro e corrigir", 2, 4)
    n("s4", "proc", "Salvar a nova senha, manter a sessão e liberar o 1º acesso", 1, 5)
    n("s5", "io", "Confirmar a troca da senha", 1, 6)
    n("fim", "end", "Fim", 1, 7)
    e("i", "a"); e("a", "t1", "Tema"); e("a", "s1", "Senha"); e("t1", "fim")
    e("s1", "s2"); e("s2", "er", "Não"); e("s2", "s3", "Sim"); e("s3", "er", "Não"); e("er", "s1")
    e("s3", "s4", "Sim"); e("s4", "s5"); e("s5", "fim")


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
    alt = linhas_y + len(FLUXOS) * 33 + 70
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{alt}" viewBox="0 0 1000 {alt}" '
           'font-family="Liberation Sans, Arial, sans-serif">', f'<rect width="1000" height="{alt}" fill="#ffffff"/>',
           f'<text x="50" y="62" font-size="28" font-weight="bold" fill="{TINTA}">Portal da Dança — Fluxogramas</text>',
           '<text x="50" y="92" font-size="14" fill="#5a5768">Versão 2.0 · 22/11/2026 · atualizada com as funções da versão 3 do sistema (RF25–RF39)</text>',
           f'<text x="50" y="{linhas_y - 12}" font-size="12" font-weight="bold" fill="#5a5768">Nº</text>',
           f'<text x="100" y="{linhas_y - 12}" font-size="12" font-weight="bold" fill="#5a5768">FLUXO</text>',
           f'<text x="455" y="{linhas_y - 12}" font-size="12" font-weight="bold" fill="#5a5768">REQUISITOS</text>',
           f'<text x="880" y="{linhas_y - 12}" font-size="12" font-weight="bold" fill="#5a5768">SITUAÇÃO</text>']
    cores = {"Atualizado": "#3157d5", "Novo": "#2f7a55", "Corrigido": "#a8461a", "Ajustado": "#a8761a", "Mantido": "#5a5768"}
    for i, f in enumerate(FLUXOS):
        y = linhas_y + 10 + i * 33
        if i % 2 == 0:
            out.append(f'<rect x="40" y="{y - 21}" width="920" height="33" fill="#f4f3f8"/>')
        out.append(f'<text x="50" y="{y}" font-size="14" font-weight="bold" fill="{TINTA}">{f["numero"]}</text>')
        out.append(f'<text x="100" y="{y}" font-size="14" fill="{TINTA}">{t(f["titulo"])}</text>')
        out.append(f'<text x="455" y="{y}" font-size="11" fill="#5a5768">{t(f["requisitos"])}</text>')
        out.append(f'<text x="880" y="{y}" font-size="13" font-weight="bold" fill="{cores[f["situacao"]]}">{f["situacao"]}</text>')
    out.append(f'<text x="50" y="{alt - 20}" font-size="12" fill="#5a5768">Legenda: elipse = início/fim · retângulo = processo · '
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
    (PASTA / "Portal_da_Danca_Fluxogramas_v2.0.drawio").write_text(drawio(), encoding="utf-8")
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
        destino = PASTA / "Portal_da_Danca_Fluxogramas_v2.0.pdf"
        subprocess.run([pdfunite, *pdfs, str(destino)], check=True)
    print(f"PDF: {destino}")


if __name__ == "__main__":
    sys.exit(main())
