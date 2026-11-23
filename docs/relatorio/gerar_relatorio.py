"""Gera o relatório final v2.0 (docx e pdf) a partir do modelo original da equipe.

    python3 docs/relatorio/gerar_relatorio.py                 # versão pública (repositório)
    python3 docs/relatorio/gerar_relatorio.py --apendices DIR # versão com os Apêndices A e B

Entradas:
  fonte/modelo_original.docx   relatório v1 da equipe, sobre o qual as alterações são aplicadas
  fonte/telas/*.png            capturas das telas do protótipo (Seção 8.3)
  ../fluxogramas/Portal_da_Danca_Fluxogramas_v2.0.pdf   página N+2 = fluxo N (Seção 7)
  DIR/ap_autorizacao.png, DIR/ap_declaracao.png        só com --apendices (dados da empresa,
                                                        fora do repositório por causa da LGPD)
Saída: Relatorio_Portal_da_Danca_v2.0.docx e .pdf nesta pasta (com --apendices, em DIR).
Requer: pdftoppm (poppler-utils), zip e LibreOffice (soffice).
"""
import argparse
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

AQUI = Path(__file__).resolve().parent
FONTE = AQUI / "fonte"
DIR_FLUXOS = AQUI.parent / "fluxogramas"
PDF_FLUXOS = DIR_FLUXOS / "Portal_da_Danca_Fluxogramas_v2.0.pdf"
NOME = "Relatorio_Portal_da_Danca_v2.0"

_args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
_args.add_argument("--apendices", type=Path, help="pasta com ap_autorizacao.png e ap_declaracao.png")
ARGS = _args.parse_args()

TMP = Path(tempfile.mkdtemp(prefix="relatorio_"))
BASE = TMP / "docx"               # modelo descompactado
SHOTS = FONTE / "telas"           # capturas das telas
subprocess.run(["unzip", "-q", str(FONTE / "modelo_original.docx"), "-d", str(BASE)], check=True)
W = BASE / "word"
doc = (W / "document.xml").read_text(encoding="utf-8")

ini = doc.index("<w:body>") + len("<w:body>")
fim = doc.index("<w:sectPr")
body = doc[ini:fim]
blocos = [m.group(0) for m in re.finditer(r"<w:(p|tbl)[ >].*?</w:\1>", body, re.S)]
assert "".join(blocos) == body, "estrutura inesperada do corpo"


def texto(el):
    return "".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", el))


def subst(i, velho, novo, n=1):
    """Troca um trecho dentro de um único <w:t> do bloco i."""
    velho_x, novo_x = escape(velho), escape(novo)
    assert blocos[i].count(velho_x) == n, (i, velho, blocos[i].count(velho_x))
    blocos[i] = blocos[i].replace(velho_x, novo_x)


def idx(prefixo):
    achados = [i for i, b in enumerate(blocos) if texto(b).startswith(prefixo)]
    assert len(achados) == 1, (prefixo, achados)
    return achados[0]


def trocar_texto_paragrafo(xml, novo):
    """Mantém a formatação do primeiro <w:t> e põe todo o texto nele."""
    ts = list(re.finditer(r"<w:t(?: [^>]*)?>[^<]*</w:t>", xml))
    primeiro = ts[0]
    xml2 = xml[:primeiro.start()] + f'<w:t xml:space="preserve">{escape(novo)}</w:t>' + xml[primeiro.end():]
    for t in ts[1:]:
        xml2 = xml2.replace(t.group(0), "", 1)
    return xml2


def bullet_com_rotulo(modelo, rotulo, resto):
    """Clona um item de lista; se o modelo tem rótulo em negrito + texto, preenche os dois."""
    ts = list(re.finditer(r"<w:t(?: [^>]*)?>[^<]*</w:t>", modelo))
    if len(ts) >= 2:
        xml = modelo[:ts[0].start()] + f'<w:t xml:space="preserve">{escape(rotulo)}</w:t>' + \
            modelo[ts[0].end():ts[1].start()] + f'<w:t xml:space="preserve">{escape(resto)}</w:t>' + \
            modelo[ts[1].end():]
        for t in ts[2:]:
            xml = xml.replace(t.group(0), "", 1)
        return xml
    return trocar_texto_paragrafo(modelo, rotulo + resto)


def nova_linha(modelo, textos):
    """Clona uma linha de tabela trocando o texto de cada célula (None mantém)."""
    cel = re.findall(r"<w:tc>.*?</w:tc>", modelo, re.S)
    for k, t in enumerate(textos):
        if t is not None:
            cel[k] = trocar_texto_paragrafo(cel[k], t)
    return re.sub(r"<w:tc>.*?</w:tc>", lambda m, it=iter(cel): next(it), modelo, flags=re.S)


RPR_CORPO = ('<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:i w:val="0"/>'
             '<w:color w:val="1E1E1E"/><w:sz w:val="22"/></w:rPr>')


def par(txt, negrito_prefixo=None, jc="both", antes=0, depois=120, keep=False):
    ppr = (f'<w:pPr>{"<w:keepNext/>" if keep else ""}<w:spacing w:before="{antes}" '
           f'w:after="{depois}" w:line="276" w:lineRule="auto"/><w:jc w:val="{jc}"/></w:pPr>')
    runs = ""
    if negrito_prefixo:
        runs += ('<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/>'
                 '<w:color w:val="1E1E1E"/><w:sz w:val="22"/></w:rPr>'
                 f'<w:t xml:space="preserve">{escape(negrito_prefixo)}</w:t></w:r>')
    runs += f'<w:r>{RPR_CORPO}<w:t xml:space="preserve">{escape(txt)}</w:t></w:r>'
    return f"<w:p>{ppr}{runs}</w:p>"


def titulo3(txt):
    return (f'<w:p><w:pPr><w:pStyle w:val="Ttulo3"/><w:keepNext/><w:spacing w:before="240" w:after="80"/></w:pPr>'
            f'<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(txt)}</w:t></w:r></w:p>')


def legenda(n, txt):
    return ('<w:p><w:pPr><w:keepNext/><w:spacing w:before="160" w:after="60"/><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:b/><w:color w:val="1E1E1E"/>'
            f'<w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">Figura {n} — </w:t></w:r>'
            '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="1E1E1E"/>'
            f'<w:sz w:val="20"/></w:rPr><w:t xml:space="preserve">{escape(txt)}</w:t></w:r></w:p>')


def fonte():
    return ('<w:p><w:pPr><w:spacing w:before="40" w:after="200"/><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="555555"/>'
            '<w:sz w:val="18"/></w:rPr><w:t>Fonte: elaborado pelos autores (2026).</w:t></w:r></w:p>')


# ---------------------------------------------------------------- imagens
rels_path = W / "_rels" / "document.xml.rels"
rels = rels_path.read_text(encoding="utf-8")
proximo_rid = max(int(x) for x in re.findall(r'Id="rId(\d+)"', rels)) + 1
proximo_docpr = max(int(x) for x in re.findall(r'<wp:docPr id="(\d+)"', doc)) + 1
(W / "media").mkdir(exist_ok=True)
novas_rels = []


def png_tamanho(p):
    with open(p, "rb") as f:
        f.read(16)
        return struct.unpack(">II", f.read(8))


def imagem(arquivo, largura_emu=5400000):
    global proximo_rid, proximo_docpr
    rid = f"rId{proximo_rid}"
    proximo_rid += 1
    destino = f"tela_{arquivo.stem}.png"
    shutil.copy(arquivo, W / "media" / destino)
    novas_rels.append(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                      f'relationships/image" Target="media/{destino}"/>')
    w, h = png_tamanho(arquivo)
    cx, cy = largura_emu, int(largura_emu * h / w)
    did = proximo_docpr
    proximo_docpr += 1
    return ('<w:p><w:pPr><w:keepNext/><w:spacing w:before="0" w:after="0"/><w:jc w:val="center"/></w:pPr><w:r><w:drawing>'
            '<wp:inline xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
            'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="{did}" name="Tela {did}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
            f'<pic:nvPicPr><pic:cNvPr id="0" name="{destino}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
            '<a:prstGeom prst="rect"/></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline>'
            '</w:drawing></w:r></w:p>')


i = idx("Integrantes:")
subst(i, "Nicolas Vendramini Dutra", "Nícolas Vendramini Dutra")

# ======================================================================
# 1. Resumo executivo
# ======================================================================
i = idx("A dispersão das informações")
subst(i, "acessado pelo navegador e operado pelo proprietário da escola.",
      "acessado pelo navegador, operado pelo proprietário da escola e com acesso controlado por papéis "
      "(Administrativo, Professor e Aluno).")
i = idx("A solução foi especificada")
subst(i, "24 requisitos funcionais, 8 requisitos não funcionais e 16 regras de negócio",
      "39 requisitos funcionais, 8 requisitos não funcionais e 20 regras de negócio")
subst(i, "e registro de auditoria em conformidade com a Lei Geral de Proteção de Dados (LGPD).",
      "controle de acesso baseado em papéis (RBAC), com portais próprios para professores e alunos; "
      "consulta dos aniversariantes do mês; cobranças de mensalidade com recebimento parcial e estorno; "
      "comunicados por aula e solicitações dos alunos; relatórios em CSV e backup dos dados; "
      "e registro de auditoria em conformidade com a Lei Geral de Proteção de Dados (LGPD).")

# ======================================================================
# 3. Investigação
# ======================================================================
i = idx("Com base nesse levantamento")
subst(i, "foram incorporados controles de autenticação, edição/exclusão",
      "foram incorporados controles de autenticação, autorização por papéis (RBAC), edição/exclusão")

# ======================================================================
# 4.1 Requisitos funcionais
# ======================================================================
i = idx("A Tabela 1 apresenta os 24")
subst(i, "os 24 requisitos funcionais", "os 39 requisitos funcionais")
t1 = idx("CódigoDescriçãoRF01")
subst(t1, "Registro de presença: O sistema deve permitir que o proprietário registre",
      "Registro de presença: O sistema deve permitir que o proprietário ou o professor responsável pela aula registre")
subst(t1, "Registro e consulta de faltas: O sistema deve permitir que o proprietário registre",
      "Registro e consulta de faltas: O sistema deve permitir que o proprietário ou o professor responsável pela aula registre")
subst(t1, "associando um professor responsável.",
      "associando um professor responsável. O professor pode agendar e alterar somente as próprias aulas (RF25).")
subst(t1, "Matrícula de alunos nas aulas: O sistema deve permitir inscrever alunos",
      "Matrícula de alunos nas aulas: O sistema deve permitir que o proprietário ou o professor responsável pela aula inscreva alunos")
subst(t1, "e permitir encerrar a sessão (logout) com segurança.",
      "direcionar cada usuário à área correspondente ao seu papel e permitir encerrar a sessão (logout) com segurança.")
subst(t1, "(podendo incluir contato, e-mail e responsável legal quando aplicável)",
      "(podendo incluir telefone, e-mail, data de nascimento e observações)")
subst(t1, "Acompanhamento de mensalidades: O sistema deve permitir que o proprietário registre e consulte as mensalidades de cada aluno, com forma de pagamento e validade/cobertura. A situação da mensalidade (em dia ou não) possui caráter exclusivamente informativo.",
      "Cobranças de mensalidades: O sistema deve permitir gerar, a cada mês, uma cobrança por matrícula ativa "
      "(mensalidade da aula combinada na matrícula, com desconto percentual ou fixo opcional e vencimento no dia 5), "
      "registrar recebimentos totais ou parciais limitados ao saldo, estornar recebimentos com motivo e cancelar "
      "cobranças sem recebimento, além de registrar mensalidades avulsas. As cobranças podem ser consultadas por "
      "competência ou por período de vencimento, com atalhos por situação (pendente, parcial, atrasada, paga ou "
      "cancelada) e exportação em CSV do recorte filtrado; a situação possui caráter exclusivamente informativo.")
subst(t1, "Correção de lançamentos financeiros: O sistema deve permitir editar ou excluir um lançamento financeiro registrado com erro,",
      "Correção de lançamentos financeiros: O sistema deve permitir editar ou excluir um lançamento financeiro registrado com erro (exceto recebimentos de cobrança, corrigidos por estorno — RN18),")
subst(t1, "incluindo o valor pago por aluno inscrito.",
      "incluindo o valor pago por aluno inscrito e, opcionalmente, a data de nascimento.")
linhas = re.findall(r"<w:tr[ >].*?</w:tr>", blocos[t1], re.S)
modelo_rf26 = [r for r in linhas if texto(r).startswith("RF24")][0]
modelo = [r for r in linhas if texto(r).startswith("RF23")][0]   # alterna o sombreado
nova = nova_linha(modelo, ["RF25",
    "Controle de acesso por papéis (RBAC): O sistema deve atribuir a cada usuário um papel — Administrativo, "
    "Professor ou Aluno — e liberar somente as funcionalidades desse papel. O Administrativo acessa todo o "
    "sistema e cria, bloqueia e define o papel dos acessos; o Professor agenda e altera as próprias aulas "
    "(respeitando a lotação da sala, o horário de funcionamento e os conflitos), vincula alunos às suas aulas, "
    "registra a chamada e consulta as presenças das suas turmas, além do próprio salário estimado; o Aluno "
    "consulta as aulas em que está matriculado, a agenda, as próprias presenças/faltas e mensalidades."])
nova += nova_linha(modelo_rf26, ["RF26",
    "Aniversariantes do mês: O sistema deve permitir que administrativos, professores e alunos consultem os "
    "alunos e professores ativos que fazem aniversário no mês, por dia, com destaque para o aniversário do "
    "dia. A data de nascimento é opcional e não pode estar no futuro; o ano de nascimento não é exibido e a "
    "idade a completar aparece somente para o Administrativo e o Professor."])
nova += nova_linha(modelo, ["RF27",
    "Consulta de frequência e oportunidades: O sistema deve permitir que o proprietário consulte, para um "
    "período de 4, 8, 12 ou 26 semanas, a ocupação real de cada aula (média de alunos presentes dividida pela "
    "capacidade da sala), classificada em faixas — quente (≥ 85%), morna (≥ 70%), fria (≥ 40%) e gelada "
    "(< 40%) —, além da tendência de frequência, da participação de alunos avulsos, das presenças por semana e "
    "das aulas candidatas a promoção."])
nova += nova_linha(modelo_rf26, ["RF28",
    "Comunicados por aula: O sistema deve permitir que o Administrativo publique comunicados em qualquer aula "
    "ativa e que o professor publique apenas nas próprias aulas; cada aluno visualiza somente os comunicados das "
    "aulas em que está matriculado."])
nova += nova_linha(modelo, ["RF29",
    "Solicitações dos alunos: O sistema deve permitir que o aluno registre solicitações (correção cadastral, "
    "revisão de frequência, alteração de matrícula ou dúvida sobre mensalidade) e acompanhe a resposta, e que o "
    "Administrativo as analise, alterando a situação (pendente, em análise, concluída ou recusada) com resposta "
    "obrigatória ao concluir ou recusar. Nenhum dado é alterado automaticamente."])
nova += nova_linha(modelo_rf26, ["RF30",
    "Preferências da conta: O sistema deve permitir que qualquer usuário altere a própria senha (informando a "
    "senha atual e respeitando as regras de senha forte) e alterne entre os temas claro e escuro."])
RF_NOVOS = [
    ("RF31", "Vários papéis na mesma conta: O sistema deve permitir que uma conta tenha mais de um papel "
     "(por exemplo, professor que também é aluno), solicitando ao entrar a escolha do ambiente e permitindo "
     "trocá-lo pelo menu; enquanto o ambiente não é escolhido, nenhuma página restrita é liberada."),
    ("RF32", "Suspensão e cancelamento de matrícula: O sistema deve permitir que o Administrativo suspenda ou "
     "cancele uma matrícula informando o motivo, preservando o histórico, e reative uma matrícula suspensa "
     "com a mesma mensalidade, respeitando a lotação da sala."),
    ("RF33", "Situação da chamada: O sistema deve controlar a chamada de cada aula e data como aberta, "
     "concluída ou cancelada, permitindo concluir a chamada, cancelar a aula com motivo e, no caso de chamada "
     "concluída, corrigir os registros somente pela administração e com motivo obrigatório."),
    ("RF34", "Relatórios do período: O sistema deve apresentar ao Administrativo indicadores de um período "
     "(frequência, chamadas, matrículas encerradas, entradas e saídas) e um quadro de mensalidades (previsto, "
     "recebido, em aberto, saldo vencido e quantidade por situação), em que cada situação leva à lista das "
     "mensalidades correspondentes, além de exportar presenças, mensalidades e movimentações em CSV."),
    ("RF35", "Backup dos dados: O sistema deve permitir que o superusuário exporte todos os dados em JSON e "
     "restaure uma exportação, com confirmação escrita, validação do arquivo e operação em transação única."),
    ("RF36", "Aulas em vários dias e vigência: O sistema deve permitir agendar uma aula em um ou mais dias da "
     "semana no mesmo horário e com período de vigência opcional, considerando todos os dias nas regras de "
     "conflito, na chamada e na geração de cobranças."),
    ("RF37", "Troca de senha no primeiro acesso: O sistema deve permitir que o Administrativo exija que o "
     "usuário troque a senha provisória no primeiro acesso, bloqueando as demais páginas até a troca."),
    ("RF38", "Alunos do professor: O sistema deve permitir que o professor consulte a lista de alunos "
     "matriculados nas próprias aulas, com contato e frequência nessas aulas."),
    ("RF39", "Criação dos usuários padrão: O sistema deve oferecer um comando de administração que crie o "
     "usuário Administrativo (responsavel) e um acesso de professor e um de aluno vinculados a cadastros "
     "existentes, sem apagar nem duplicar dados, podendo ser executado novamente; a senha informada passa "
     "pelas regras de senha forte e pode exigir troca no primeiro acesso."),
]
for k, (cod, desc) in enumerate(RF_NOVOS):
    nova += nova_linha(modelo if k % 2 == 0 else modelo_rf26, [cod, desc])
blocos[t1] = blocos[t1].replace("</w:tbl>", nova + "</w:tbl>")

# ======================================================================
# 4.2 RNF
# ======================================================================
t2 = idx("CódigoDescriçãoRNF01")
subst(t2, "sem credenciais ou chaves expostas no código-fonte.",
      "sem credenciais ou chaves expostas no código-fonte; além disso, cada página deve ser autorizada no "
      "servidor conforme o papel do usuário, com negação por padrão (RF25).")
subst(t2, "contraste visual adequado (mínimo de 4,5:1 para texto comum).",
      "contraste visual adequado (mínimo de 4,5:1 para texto comum), com tema claro e tema escuro opcional.")
subst(t2, "exclusivamente à equipe autorizada.",
      "exclusivamente à equipe autorizada; cada perfil deve visualizar apenas os dados pessoais necessários "
      "à sua função (o aluno vê somente os próprios dados e o professor, os das suas turmas; na lista de "
      "aniversariantes, o ano de nascimento não é exibido e a idade aparece apenas ao Administrativo e ao Professor).")

# ======================================================================
# 4.3 Regras de negócio
# ======================================================================
i = idx("Complementarmente aos requisitos funcionais")
subst(i, "as 16 regras de negócio", "as 20 regras de negócio")
t3 = idx("CódigoRegra e DescriçãoRN01")
linhas = re.findall(r"<w:tr[ >].*?</w:tr>", blocos[t3], re.S)
modelo = [r for r in linhas if texto(r).startswith("RN15")][0]
nova = nova_linha(modelo, ["RN17",
    "Escopo de acesso por papel: Toda página é negada por padrão e liberada apenas aos papéis autorizados. "
    "O professor só agenda, altera, vincula alunos e registra chamada nas aulas em que é o responsável, sem "
    "poder atribuí-las a outro professor; desativar ou remover aulas e cadastrar alunos, professores, "
    "modalidades e salas é exclusivo do Administrativo. O aluno visualiza somente os próprios dados. "
    "Usuários bloqueados não acessam o sistema, e os registros de auditoria são preservados."])
modelo_rn18 = [r for r in linhas if texto(r).startswith("RN16")][0]
nova += nova_linha(modelo_rn18, ["RN18",
    "Cobranças de mensalidade: Cada matrícula ativa gera no máximo uma cobrança por mês, no valor da mensalidade "
    "combinada na matrícula (copiada da aula no momento da inscrição) menos o desconto percentual (0 a 100%) ou "
    "fixo (até o valor da mensalidade). A cobrança não altera o caixa; só os recebimentos entram no saldo. O "
    "recebimento não pode exceder o saldo devedor; recebimentos não são editados nem excluídos — a correção é "
    "feita por estorno com motivo obrigatório, registrado como saída, preservando o histórico. A cobrança só pode "
    "ser cancelada sem recebimentos ativos."])
modelo_rn15 = [r for r in linhas if texto(r).startswith("RN15")][0]
nova += nova_linha(modelo_rn15, ["RN19",
    "Conclusão e correção da chamada: O professor registra e conclui a chamada das próprias aulas, mas não "
    "altera uma chamada concluída; a correção posterior cabe à administração e exige motivo, registrado na "
    "chamada e na auditoria. A aula só pode ser cancelada em uma data sem registros, com motivo, e uma chamada "
    "concluída ou cancelada só volta a ficar aberta por decisão da administração."])
nova += nova_linha(modelo_rn18, ["RN20",
    "Encerramento de matrícula: Toda matrícula encerrada tem situação — suspensa, cancelada ou encerrada (vínculo "
    "removido) — e as duas primeiras exigem motivo. Matrículas encerradas não geram novas cobranças, mas "
    "continuam valendo para o salário do mês em que estiveram ativas (RN16). Somente a matrícula suspensa pode "
    "ser reativada, com nova data de início e a mesma mensalidade."])
blocos[t3] = blocos[t3].replace("</w:tbl>", nova + "</w:tbl>")
subst(t3, "Prefeitura e salários dos professores.",
      "Prefeitura e salários dos professores. Estornos de mensalidade são saídas próprias, geradas a partir do recebimento estornado (RN18).")
subst(t3, "e a situação da mensalidade é apenas informativa.",
      "e a situação da mensalidade ou da cobrança (pendente, parcial, atrasada ou paga) é apenas informativa.")

# ======================================================================
# 5. Visão geral — perfis
# ======================================================================
i = idx("Em alinhamento com o modelo operacional")
blocos[i] = trocar_texto_paragrafo(blocos[i],
    "Em alinhamento com o modelo operacional da escola levantado no diagnóstico, o acesso à solução é "
    "controlado por papéis (RBAC — RF25 e RN17), com os seguintes perfis de usuário (os três consultam os "
    "aniversariantes do mês — RF26):")
b_prop = idx("Proprietário (Responsável Administrativo")
b_eq = idx("Equipe Técnica / Administração do Sistema")
modelo_bullet = blocos[b_prop]
blocos[b_prop] = bullet_com_rotulo(modelo_bullet, "Administrativo (Proprietário / secretaria da escola): ",
    "usuário principal da aplicação, com permissão para realizar todos os cadastros, agendamentos, "
    "matrículas, chamadas, lançamentos financeiros, correções, cálculo de salários e consultas de saldo e "
    "balanço, cobranças de mensalidade (geração, recebimento, estorno e desconto), comunicados e respostas às "
    "solicitações dos alunos, relatórios e suspensão ou cancelamento de matrículas, além de criar, bloquear e "
    "definir os papéis dos acessos (uma conta pode ter mais de um papel e escolhe o ambiente ao entrar; a "
    "senha provisória pode exigir troca no primeiro acesso).")
blocos[b_eq] = "".join([
    bullet_com_rotulo(modelo_bullet, "Professor: ",
        "acessa o Portal do Professor com as próprias aulas, os alunos inscritos e o salário estimado do mês; "
        "agenda e altera somente as próprias aulas, respeitando a lotação da sala, o horário de funcionamento "
        "e os conflitos de sala e professor; vincula alunos às suas aulas até a capacidade da sala; registra "
        "e conclui a chamada, consulta as presenças e a lista de alunos das suas turmas e publica comunicados "
        "para as próprias aulas."),
    bullet_com_rotulo(modelo_bullet, "Aluno: ",
        "acessa o Portal do Aluno para consultar as aulas em que está matriculado, a agenda da escola, o "
        "próprio histórico de presenças e faltas, as próprias cobranças e os comunicados das suas aulas, e abre "
        "solicitações à administração, sem acesso aos dados de outros alunos."),
    bullet_com_rotulo(modelo_bullet, "Equipe Técnica / Administração do Sistema: ",
        "usuários administrativos marcados como equipe técnica são os únicos que visualizam os registros de "
        "auditoria de acessos e alterações (RF24 e RNF04), assegurando governança e conformidade com a LGPD."),
])
i = idx("Ressalta-se que funcionalidades")
subst(i, "cobrança online integrada a gateways bancários e portais individuais para alunos ou professores não fazem parte",
      "pagamento online integrado a gateways bancários e alteração direta de dados pelo aluno (o aluno registra "
      "pedidos em Solicitações, analisados pela administração) não fazem parte")

# ======================================================================
# 6. Módulos (Tabela 4)
# ======================================================================
t4 = idx("MóduloFuncionalidades Agrupadas")
subst(t4, "encerramento de sessão (logout) e registro automático de eventos de acesso.",
      "encerramento de sessão (logout), controle de acesso por papéis (Administrativo, Professor e Aluno) "
      "com negação por padrão e registro automático de eventos de acesso.")
subst(t4, "RF22, RF24, RNF03", "RF22, RF24, RF25, RF30, RF31, RF37, RF39, RNF03, RN17")
subst(t4, "edição cadastral e visualização consolidada de aulas, presenças e mensalidades.",
      "edição cadastral, visualização consolidada de aulas, presenças e mensalidades e lista de "
      "aniversariantes do mês (alunos e professores).")
subst(t4, "RF01, RF02, RN08", "RF01, RF02, RF26, RN08")
subst(t4, "chamada diária com alunos avulsos e consulta filtrada de frequência.",
      "chamada diária com alunos avulsos, consulta filtrada de frequência e consulta de ocupação e "
      "oportunidades por aula.")
subst(t4, "RF03–RF05, RF18–RF21,", "RF03–RF05, RF18–RF21, RF27, RF28, RF32, RF33, RF36,")
subst(t4, "chamada diária com alunos avulsos, consulta filtrada de frequência e consulta de ocupação e "
      "oportunidades por aula.", "chamada diária com alunos avulsos, consulta filtrada de frequência, consulta de ocupação e "
      "oportunidades por aula, comunicados por aula, aulas em vários dias com vigência, situação da chamada e "
      "suspensão/cancelamento de matrículas.")
subst(t4, "acompanhamento informativo de mensalidades,", "cobranças de mensalidade com desconto, recebimento parcial e estorno,")
subst(t4, "RF06–RF16, RF23, RN01–RN07, RN11, RN12, RN16", "RF06–RF16, RF23, RN01–RN07, RN11, RN12, RN16, RN18")
subst(t4, "RF01, RF02, RF26, RN08", "RF01, RF02, RF26, RF29, RN08")
subst(t4, "Listagem de usuários do sistema e consulta", "Criação, bloqueio e definição do papel dos acessos, "
      "listagem de usuários e consulta")
subst(t4, "restrita à equipe.", "esta última restrita à equipe técnica.")
linhas = re.findall(r"<w:tr[ >].*?</w:tr>", blocos[t4], re.S)
ult = [r for r in linhas if texto(r).startswith("6. Administração")][0]
blocos[t4] = blocos[t4].replace(ult, ult.replace(escape("RF24, RNF04"), escape("RF24, RF25, RF34, RF35, RNF04")))
subst(t4, "esta última restrita à equipe técnica.", "esta última restrita à equipe técnica; relatórios em CSV e backup dos dados.")
subst(t4, "RF17, RN07", "RF17, RF38, RN07")
for nome, txt in [("2. Alunos", "RF01, RF02, RN08"), ("3. Professores", "RF17, RN07")]:
    pass  # portais estão no módulo 1 e nas telas; tabelas 2 e 3 permanecem

# ======================================================================
# 7. Fluxogramas v2.0: os 26 fluxos (00 a 25), imagens do PDF de fluxogramas
# ======================================================================
FLUXOS_JSON = {f["numero"]: f for f in json.loads((DIR_FLUXOS / "fluxos.json").read_text(encoding="utf-8"))}
assert sorted(FLUXOS_JSON) == [f"{k:02d}" for k in range(26)], "fluxos.json deve ter os fluxos 00 a 25"
PNG_FLUXOS = TMP / "fluxos"
PNG_FLUXOS.mkdir()
for num in FLUXOS_JSON:          # página 1 = índice; página N+2 = fluxo N
    pag = str(int(num) + 2)
    subprocess.run(["pdftoppm", "-r", "192", "-png", "-singlefile", "-f", pag, "-l", pag,
                    str(PDF_FLUXOS), str(PNG_FLUXOS / f"fluxo_{num}")], check=True)
LARG_FLUXO, ALT_FLUXO = 5_400_000, 4_400_000  # cabe na página com título, texto e legenda


def largura_fluxo(png):
    pw, ph = png_tamanho(png)
    return int(min(LARG_FLUXO, ALT_FLUXO * pw / ph))


def titulo_fluxo_txt(num):
    f = FLUXOS_JSON[num]
    return f"Fluxo {num} — {f['titulo']} (Requisitos: {', '.join(f['requisitos'])})"


# Fluxos que já estavam no modelo: troca a imagem pela v2.0 e mantém o texto.
rels_doc = (W / "_rels" / "document.xml.rels").read_text(encoding="utf-8")
num_atual = None
for k, b in enumerate(blocos):
    t = texto(b)
    if t.startswith("Fluxo ") and "Ttulo2" in b:
        num_atual = t[6:8]
    elif t.startswith("8. PROTÓTIPO"):
        break
    elif num_atual and "<w:drawing" in b:
        rid = re.search(r'r:embed="(rId\d+)"', b).group(1)
        alvo = re.search(rf'Id="{rid}"[^>]*Target="(media/[^"]+)"', rels_doc).group(1)
        png = PNG_FLUXOS / f"fluxo_{num_atual}.png"
        shutil.copy(png, W / alvo)
        pw, ph = png_tamanho(png)
        ncx = largura_fluxo(png)
        ncy = int(ncx * ph / pw)
        cx, cy = map(int, re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"/>', b).groups())
        blocos[k] = b.replace(f'cx="{cx}" cy="{cy}"', f'cx="{ncx}" cy="{ncy}"')
        num_atual = None

i = idx("Esta seção apresenta os 8 fluxogramas")
blocos[i] = trocar_texto_paragrafo(blocos[i],
    "Esta seção apresenta os 26 fluxogramas do sistema da Portal da Dança, na versão 2.0 (fluxos 00 a 25), "
    "que cobrem todas as operações modeladas no projeto: o acesso com papéis; os cadastros de alunos, "
    "professores, modalidades e salas; o agendamento de aulas com validação de conflitos, a matrícula com "
    "histórico e a chamada diária com alunos avulsos; o registro de receitas e despesas, as cobranças de "
    "mensalidade com recebimento parcial e estorno, o cálculo salarial docente, as consultas e o balanço "
    "financeiro mensal; a correção de lançamentos e a auditoria; a frequência e as oportunidades de promoção; "
    "os comunicados, as solicitações, os relatórios, o backup, os aniversariantes, os alunos do professor, a "
    "criação dos usuários padrão e as preferências da conta. Cada fluxo indica os requisitos que atende, e a "
    "correspondência entre requisitos, fluxos e telas está na Tabela 5 (Seção 8.4). Os arquivos editáveis "
    "(draw.io) e o PDF dos fluxogramas estão na pasta docs/fluxogramas do repositório e no menu Documentação "
    "do sistema.")

i = idx("Fluxo 04 — Agendamento de aulas")
subst(i, "(Requisitos: RF19, RF20, RN09, RN10, RN13, RN14, RN15)",
      "(Requisitos: RF19, RF20, RF36, RN09, RN10, RN13, RN14, RN15, RN17)")
subst(i + 1, "a disponibilidade de sala e professor.",
      "a disponibilidade de sala e professor, em um ou mais dias da semana e com vigência opcional; o "
      "professor agenda e altera apenas as próprias aulas.")
subst(i + 2, "modalidade, dia da semana, horário de início/fim, sala e professor.",
      "modalidade, dias da semana, horário de início/fim, sala, professor, mensalidade e vigência (opcional).")
subst(i + 3, "caso existente, decidir entre alterar, desativar ou remover;",
      "caso existente, decidir entre alterar, desativar ou remover (as duas últimas, exclusivas do Administrativo);")
subst(i + 3, "com término posterior ao início; verificar se sala e professor estão livres no horário;",
      "com término posterior ao início e vigência coerente; verificar se sala e professor estão livres em "
      "todos os dias escolhidos;")
subst(i + 4, "Aula salva e disponível na agenda,", "Aula salva e disponível na agenda em cada dia escolhido,")

i = idx("Fluxo 05 — Matrícula de alunos nas aulas")
subst(i, "(Requisitos: RF20, RF21, RF24, RN07, RN08, RN09)",
      "(Requisitos: RF20, RF21, RF24, RF32, RN07, RN08, RN09, RN18, RN20)")
subst(i + 1, "utilizado no cálculo salarial sem bloquear a participação avulsa.",
      "utilizado nas cobranças e no cálculo salarial sem bloquear a participação avulsa, além de ajustar a "
      "mensalidade e o desconto da matrícula, suspendê-la ou cancelá-la com motivo e reativar a matrícula suspensa.")
subst(i + 2, "desmarcação de alunos que saíram.",
      "desmarcação de alunos que saíram; na gestão de uma matrícula, mensalidade e desconto (percentual ou "
      "fixo) ou tipo de encerramento (suspensão ou cancelamento) e motivo.")
subst(i + 3, "permanece menor ou igual à capacidade da sala vinculada.",
      "permanece menor ou igual à capacidade da sala vinculada; escolher entre vincular alunos ou gerenciar "
      "uma matrícula (ajustar valor, encerrar ou reativar); na reativação, conferir se a matrícula está "
      "suspensa, se a aula está ativa e se há vaga.")
subst(i + 4, "disponibilização dos vínculos para o cálculo salarial.",
      "disponibilização dos vínculos para as cobranças (Fluxo 10) e o cálculo salarial (Fluxo 11); "
      "matrículas suspensas ou canceladas guardam o motivo e deixam de gerar cobranças.")

i = idx("Fluxo 06 — Registro de presença e faltas")
subst(i, "(Requisitos: RF03, RF04, RF21, RN08)", "(Requisitos: RF03, RF04, RF21, RF33, RN08, RN19)")
subst(i + 1, "respeitando o dia da semana da aula e a capacidade máxima da sala.",
      "respeitando os dias e a vigência da aula e a capacidade máxima da sala, e controlar a situação da "
      "chamada (aberta, concluída ou cancelada).")
subst(i + 2, "eventual inclusão ou remoção de alunos avulsos.",
      "eventual inclusão ou remoção de alunos avulsos; motivo, no cancelamento da aula ou na correção de "
      "chamada concluída.")
subst(i + 3, "corresponde ao dia da semana da aula;",
      "corresponde a um dia da aula dentro da vigência; verificar a situação da chamada — a concluída só é "
      "corrigida pela administração, com motivo; decidir se a aula será cancelada (somente sem registros);")
subst(i + 3, "não excede a capacidade da sala.",
      "não excede a capacidade da sala; decidir se a chamada será concluída.")
subst(i + 4, "Gravação individualizada dos registros de presença e falta por aluno e data.",
      "Gravação individualizada dos registros de presença e falta por aluno e data, com a chamada aberta ou "
      "concluída; aula cancelada com motivo; correções registradas com motivo na chamada e na auditoria.")

# ======================================================================
# 7. Fluxogramas: fluxos que não estavam no modelo (texto + imagem v2.0)
# ======================================================================
# (objetivo, dados de entrada, principais decisões, resultado esperado)
TEXTOS_FLUXOS = {
    "00": (
        "Controlar a entrada no sistema por usuário e senha, aplicando a troca obrigatória da senha provisória, "
        "a escolha do ambiente quando a conta tem mais de um papel e a liberação de cada página apenas ao papel "
        "ativo, com registro de todos os acessos.",
        "Usuário e senha; nova senha (no primeiro acesso); ambiente escolhido (Administrativo, Professor ou "
        "Aluno), quando a conta tem vários papéis; página solicitada.",
        "Verificar se o usuário já está autenticado; validar a senha e se a conta está ativa; verificar se há "
        "troca de senha pendente; verificar se a conta tem mais de um papel; verificar se o papel ativo pode ver "
        "a página; verificar se o usuário pediu para sair.",
        "Página exibida ao papel autorizado ou acesso negado (403); login, falha de login, cada acesso (usuário, "
        "IP e página) e logout registrados na auditoria."),
    "02": (
        "Cadastrar professores e consultar ou atualizar seus dados, incluindo o valor pago por aluno inscrito, "
        "que é a base do cálculo salarial (Fluxo 11).",
        "Operação desejada (cadastrar ou selecionar um professor); nome, contato e valor por aluno inscrito "
        "(R$/mês).",
        "Escolher entre cadastrar ou selecionar um professor; validar se os dados estão completos e se o valor é "
        "maior ou igual a zero; decidir entre consultar ou atualizar o cadastro.",
        "Professor cadastrado ou atualizado; na consulta, exibição dos dados, das aulas e do salário estimado do "
        "mês."),
    "03": (
        "Manter o cadastro das modalidades de dança e das salas (com capacidade) usadas no agendamento das aulas, "
        "impedindo a remoção de registros em uso.",
        "Operação (cadastrar ou manter); nome da modalidade ou da sala e, para a sala, a capacidade.",
        "Escolher entre cadastrar ou manter um registro; validar se o nome é único e se a capacidade é de pelo "
        "menos 1; escolher entre atualizar ou remover; na remoção, verificar se a modalidade ou sala é usada por "
        "alguma aula agendada.",
        "Modalidade ou sala cadastrada, atualizada ou removida; quando há aula usando o registro, aviso de que "
        "ele não pode ser removido."),
    "07": (
        "Consultar os registros de presença e falta com filtros, separando a consulta do registro da chamada "
        "(Fluxo 06).",
        "Filtros opcionais por aluno, aula, situação (presente ou falta) e período.",
        "Validar as datas do filtro; verificar se há registros para os filtros escolhidos.",
        "Lista dos registros com os totais de presenças e faltas, ou aviso de que não há registros."),
    "10": (
        "Gerar a cobrança mensal de cada matrícula ativa e controlar seus recebimentos, inclusive parciais, "
        "estornos e cancelamentos, mantendo a situação da mensalidade apenas informativa.",
        "Mês ou período e situação, na consulta; no recebimento, valor, data e forma de pagamento; no estorno ou "
        "no cancelamento, o motivo.",
        "Escolher a operação (gerar cobranças, exportar CSV ou abrir uma cobrança); escolher entre receber, "
        "estornar ou cancelar; validar se o valor recebido é maior que zero e não ultrapassa o saldo devedor; no "
        "cancelamento, verificar se a cobrança tem recebimentos ativos.",
        "Uma cobrança por matrícula ativa no mês (mensalidade menos desconto, vencimento no dia 5), sem alterar o "
        "caixa; recebimento lançado como entrada vinculada (origem mensalidade) e estorno como saída vinculada; "
        "situação atualizada (pendente, parcial, atrasada ou paga); CSV com os filtros escolhidos."),
    "12": (
        "Consultar as entradas e saídas registradas em um período e exibir o saldo financeiro atual da escola.",
        "Tipo de consulta (movimentações ou saldo); período, tipo de lançamento e texto de busca (opcionais).",
        "Escolher entre consultar as movimentações ou o saldo; validar se a data inicial é menor ou igual à "
        "final.",
        "Lista das entradas e saídas do período, ou saldo atual (soma de todas as entradas menos todas as "
        "saídas)."),
    "14": (
        "Consultar as aulas ativas da semana, em substituição ao controle de entrada e saída de alunos (a escola "
        "não tem catraca).",
        "Filtros opcionais por dia, modalidade e sala.",
        "Verificar se há aulas que correspondem aos filtros.",
        "Agenda por dia com horário, aula, sala, professor e inscritos/capacidade, ou aviso de que não há aulas "
        "correspondentes."),
    "15": (
        "Corrigir ou excluir um lançamento financeiro digitado errado, mantendo o registro da alteração na "
        "auditoria.",
        "Lançamento selecionado na consulta de movimentações (Fluxo 12); novos dados ou confirmação da exclusão.",
        "Escolher entre editar ou excluir; validar os dados alterados; confirmar a exclusão.",
        "Lançamento alterado, excluído ou mantido; alteração registrada na auditoria; saldo e balanço "
        "recalculados."),
    "16": (
        "Permitir que apenas a equipe consulte a auditoria de acessos e alterações, que contém dados pessoais "
        "(IP e histórico de acesso).",
        "Acesso à área de Administração.",
        "Verificar se o usuário é da equipe.",
        "Para a equipe, resumo dos últimos 30 dias (usuários, IPs, logins e falhas) e listas de logins, logouts e "
        "alterações de dados, gravados nos Fluxos 00, 05 e 15; para os demais, apenas a lista de usuários."),
    "17": (
        "Medir a ocupação real de cada aula e indicar ao proprietário as aulas que precisam de promoção ou que "
        "comportam uma nova turma.",
        "Período de análise (4, 8, 12 ou 26 semanas).",
        "Verificar se a aula tem chamada no período; classificar a ocupação (média de presentes ÷ capacidade da "
        "sala): a partir de 70%, quente ou morna, sem promoção (a partir de 85%, avaliar nova turma); abaixo de "
        "70%, fria ou gelada, com promoção (abaixo de 40%, promoção forte).",
        "Mapa de calor, ranking, oportunidades e sugestões, considerando também a tendência, a frequência e os "
        "alunos avulsos; aulas sem chamada no período aparecem como “sem dados”."),
    "18": (
        "Publicar avisos por aula e mostrá-los aos alunos matriculados, conforme o papel do usuário.",
        "Aula, título e mensagem (Administrativo ou Professor).",
        "Identificar o papel ativo; verificar se a aula é permitida (o professor publica só nas próprias aulas e o "
        "Administrativo em qualquer aula ativa) e se os campos estão preenchidos.",
        "Comunicado publicado com autor e data e visível aos alunos matriculados na aula; o aluno vê os "
        "comunicados das suas aulas, do mais recente ao mais antigo."),
    "19": (
        "Registrar os pedidos dos alunos e permitir que a administração os analise e responda.",
        "Para o aluno, tipo (cadastro, frequência, matrícula ou mensalidade) e descrição; para o Administrativo, "
        "filtro por situação, nova situação e resposta.",
        "Identificar o papel ativo; verificar se a descrição foi informada; exigir resposta quando a solicitação é "
        "concluída ou recusada.",
        "Solicitação registrada como pendente e acompanhada pelo aluno; situação e resposta salvas pela "
        "administração, sem alterar automaticamente outros dados."),
    "20": (
        "Reunir os indicadores de um período e o quadro de mensalidades, com acesso às listas já filtradas e "
        "exportação em CSV.",
        "Período (de/até) ou atalho; situação escolhida no quadro de mensalidades; tipo de CSV.",
        "Validar se a data inicial é menor ou igual à final; escolher a próxima ação (abrir a lista de uma "
        "situação ou baixar um CSV).",
        "Indicadores de frequência, chamadas, matrículas encerradas, entradas e saídas; mensalidades previstas, "
        "recebidas, em aberto, saldo vencido e quantidade por situação; lista de mensalidades filtrada ou CSV de "
        "presenças, mensalidades ou movimentações."),
    "21": (
        "Exportar todos os dados do sistema e restaurá-los com segurança, apenas pelo superusuário.",
        "Escolha entre exportar ou restaurar; na restauração, o arquivo .json (até 50 MB) e a palavra RESTAURAR "
        "como confirmação.",
        "Verificar se o usuário é superusuário; escolher entre exportar ou restaurar; validar a confirmação e o "
        "arquivo; verificar se a restauração terminou sem erro.",
        "Arquivo JSON baixado (contém dados pessoais) e registro BACKUP_EXPORTADO na auditoria; ou dados "
        "substituídos em transação única, registro BACKUP_RESTAURADO e sessão encerrada; em caso de erro, nenhum "
        "dado é alterado."),
    "22": (
        "Listar os alunos e professores ativos que fazem aniversário no mês, sem expor o ano de nascimento.",
        "Mês (padrão: mês atual).",
        "Verificar se há aniversariantes; verificar se o papel é Administrativo ou Professor, os únicos que veem "
        "a idade a completar.",
        "Lista ordenada por dia, com destaque para o aniversário do dia e a idade exibida só ao Administrativo e "
        "ao Professor, ou aviso de que não há aniversariantes."),
    "23": (
        "Mostrar ao professor apenas os alunos matriculados nas próprias aulas, com contato e frequência.",
        "Acesso a Meus alunos pelo usuário com papel Professor.",
        "Verificar se o usuário está vinculado a um professor ativo; verificar se há alunos matriculados.",
        "Lista com aluno, contato, aulas e frequência nessas aulas; aviso de que não há alunos; ou acesso negado "
        "quando o usuário não está vinculado a um professor."),
    "24": (
        "Criar, por comando de terminal, os acessos padrão do sistema — o responsavel (Administrativo) e um "
        "acesso de professor e um de aluno ligados a cadastros existentes —, sem apagar nem duplicar dados.",
        "Comando portal.py usuarios, com as opções --senha, --trocar-senha e --redefinir.",
        "Verificar se a senha foi informada (senão, gerar uma senha aleatória, exibida uma vez); verificar se o "
        "usuário responsavel já existe; para Professor e Aluno, verificar se o cadastro escolhido já tem acesso.",
        "Usuários criados ou mantidos (a senha só muda com --redefinir), ligados ao papel e ao cadastro, com troca "
        "de senha no primeiro acesso quando pedida; resumo com login, papel, cadastro e situação de cada usuário. "
        "O comando pode ser executado novamente."),
    "25": (
        "Permitir que qualquer usuário troque a própria senha e alterne entre o tema claro e o escuro.",
        "Senha atual, nova senha e confirmação; ou a escolha do tema.",
        "Escolher entre alterar a senha ou o tema; verificar se a senha atual está correta; validar se a nova "
        "senha é forte e se a confirmação é igual.",
        "Nova senha salva, mantendo a sessão e liberando o primeiro acesso (Fluxo 00); ou tema alternado e "
        "guardado no navegador."),
}
ROTULOS = ("Objetivo: ", "Dados de entrada: ", "Principais decisões: ", "Resultado esperado: ")

# Separa a seção 7 em grupos (um por fluxo) e insere os novos na ordem numérica.
ini7 = idx("Fluxo 01 — Cadastro e consulta de alunos")
fim7 = idx("8. PROTÓTIPO DA SOLUÇÃO")
grupos, atual = {}, None
for k in range(ini7, fim7):
    t = texto(blocos[k])
    if t.startswith("Fluxo ") and "Ttulo2" in blocos[k]:
        atual = t[6:8]
        grupos[atual] = []
    grupos[atual].append(blocos[k])
ultimo = max(grupos)                      # o que vem depois da figura do último fluxo fica no fim
corte = max(j for j, b in enumerate(grupos[ultimo]) if "<w:drawing" in b) + 1
sobra, grupos[ultimo] = grupos[ultimo][corte:], grupos[ultimo][:corte]

modelo_titulo = grupos["01"][0]
modelo_itens = grupos["01"][1:5]
assert [texto(b).split(":")[0] + ": " for b in modelo_itens] == list(ROTULOS)
assert set(TEXTOS_FLUXOS) == set(FLUXOS_JSON) - set(grupos), "texto faltando ou sobrando na Seção 7"
for num, itens in TEXTOS_FLUXOS.items():
    png = PNG_FLUXOS / f"fluxo_{num}.png"
    grupos[num] = ([trocar_texto_paragrafo(modelo_titulo, titulo_fluxo_txt(num))]
                   + [bullet_com_rotulo(m, r, txt) for m, r, txt in zip(modelo_itens, ROTULOS, itens)]
                   + [imagem(png, largura_emu=largura_fluxo(png))])
for num, grupo in grupos.items():         # o título segue o fluxos.json (requisitos atualizados)
    assert texto(grupo[0]) == titulo_fluxo_txt(num), (texto(grupo[0]), titulo_fluxo_txt(num))
blocos[ini7:fim7] = [b for num in sorted(grupos) for b in grupos[num]] + sobra

# ======================================================================
# 7. Fluxogramas: legendas numeradas (Figuras 1–26)
# ======================================================================
n_fig = 0
novos = []
titulo_fluxo = None
for b in blocos:
    t = texto(b)
    if t.startswith("Fluxo ") and "Ttulo2" in b:
        titulo_fluxo = t.split(" (Requisitos")[0]
        # cada fluxograma começa em página nova (título, texto e figura juntos)
        if "<w:pageBreakBefore/>" not in b:
            b = b.replace('<w:pStyle w:val="Ttulo2"/>', '<w:pStyle w:val="Ttulo2"/><w:pageBreakBefore/>', 1)
    if "<w:drawing" in b:
        n_fig += 1
        # fluxogramas altos: 88% para título, texto, legenda e figura caberem na página
        cx, cy = map(int, re.search(r'<wp:extent cx="(\d+)" cy="(\d+)"/>', b).groups())
        if cy > 5100000:
            ncx, ncy = int(cx * 0.88), int(cy * 0.88)
            b = b.replace(f'cx="{cx}" cy="{cy}"', f'cx="{ncx}" cy="{ncy}"')
        novos.append(legenda(n_fig, f"Fluxograma do {titulo_fluxo}"))
        novos.append(b.replace('<w:pPr><w:spacing w:before="80" w:after="200"/>',
                               '<w:pPr><w:keepNext/><w:spacing w:before="0" w:after="0"/>', 1))
        novos.append(fonte())
        continue
    novos.append(b)
blocos = novos
assert n_fig == 26

# ======================================================================
# 8.1 Apresentação do protótipo
# ======================================================================
i = idx("O protótipo da solução foi estruturado")
subst(i, "contemplando os seis módulos funcionais definidos na Seção 6 (Acesso, Alunos, Professores, Aulas, Financeiro e Administração).",
      "contemplando os seis módulos funcionais definidos na Seção 6 (Acesso, Alunos, Professores, Aulas, "
      "Financeiro e Administração) e o controle de acesso por papéis (Administrativo, Professor e Aluno).")
subst(i, "a aplicação é executada via servidor web integrado (endereço local http://localhost:3010), tendo sido submetida a 132 testes automatizados",
      "a aplicação é instalada e iniciada pelo script portal.py (comandos instalar e iniciar) e acessada pelo "
      "endereço local http://127.0.0.1:8000, tendo sido submetida a 234 testes automatizados")
subst(i, "de requisitos e 188 verificações estáticas de segurança (Semgrep).",
      "de requisitos e à análise estática de segurança com o Semgrep 1.56 (268 regras dos conjuntos p/python, "
      "p/django, p/security-audit e p/secrets, em 321 arquivos). Os 27 alertas emitidos foram revisados um a "
      "um e classificados como falsos positivos: 25 apontam links gerados pelo próprio servidor (URLs internas "
      "das telas), 1 a conversão da documentação em Markdown, que escapa todo o texto antes de exibi-lo, e 1 ao "
      "formulário de login, que contém o token CSRF (um envio sem o token é recusado); não restou "
      "vulnerabilidade aberta. A interface segue o protótipo visual v3 da equipe (menu lateral com o perfil "
      "ativo, cartões de indicadores e tema claro/escuro), adaptado ao sistema em Django.")
i = idx("Link de acesso / repositório do protótipo:")
blocos[i] = blocos[i].replace("</w:p>",
    '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:color w:val="0C4975"/><w:sz w:val="22"/>'
    '</w:rPr><w:t xml:space="preserve"> https://github.com/rasollo/escoladedanca</w:t></w:r></w:p>', 1) \
    if texto(blocos[i]).strip().endswith(":") else blocos[i]

# ======================================================================
# 8.2 Organização das telas
# ======================================================================
i = idx("A navegação do protótipo organiza-se")
subst(i, "que direciona o usuário autenticado ao menu principal dividido por áreas operacionais, conforme descrito a seguir:",
      "que direciona o usuário autenticado à área do seu papel: o Administrativo ao menu principal dividido por "
      "áreas operacionais, o Professor ao Portal do Professor e o Aluno ao Portal do Aluno, conforme descrito a seguir:")
i = idx("Matrículas e Frequência (RF03, RF04, RF21)")
blocos[i] = blocos[i].replace(escape("(RF03, RF04, RF21)"), escape("(RF03, RF04, RF21, RF32, RF33)"), 1)
subst(i, "consulta filtrada de presenças e faltas.",
      "consulta filtrada de presenças e faltas; chamada aberta, concluída ou cancelada, com correção "
      "justificada, e suspensão ou cancelamento de matrículas com motivo.")
i = idx("Modalidades, Salas e Agenda de Aulas")
blocos[i] = blocos[i].replace(escape("(RF05, RF18, RF19, RF20)"), escape("(RF05, RF18, RF19, RF20, RF36)"), 1)
i = idx("Financeiro, Mensalidades e Salários")
subst(i, "acompanhamento informativo de mensalidades,", "cobranças de mensalidade (geração mensal, recebimento parcial, estorno e cancelamento),")
blocos[i] = blocos[i].replace(escape("(RF06–RF16, RF23)"), escape("(RF06–RF16, RF23, RN18)"), 1)
i = idx("Administração e Auditoria (RF24)")
blocos[i] = bullet_com_rotulo(blocos[i], "Administração e Auditoria (RF24, RF25): ",
    "tela de gestão dos acessos (criação de usuários com papel e vínculo ao cadastro do professor ou do aluno, "
    "bloqueio e desbloqueio) e, restrita à equipe técnica, trilha de auditoria (logins, falhas, logouts e "
    "alterações com usuário, IP, data e hora).")
modelo_82 = blocos[i]
blocos[i] = blocos[i] + "".join([
    bullet_com_rotulo(modelo_82, "Portal do Professor (RF25): ",
        "área com as aulas do professor, inscritos e lotação de cada sala, salário estimado e pagamentos "
        "recebidos, com atalhos para agendar aula, vincular alunos e fazer a chamada das próprias turmas, e "
        "lista dos seus alunos com contato e frequência (RF38)."),
    bullet_com_rotulo(modelo_82, "Consultas de frequência e oportunidades (RF27): ",
        "painel do Administrativo com a ocupação real de cada aula por faixa de temperatura, tendência, "
        "presenças por semana e sugestões de promoção para as aulas com sobra de lugares."),
    bullet_com_rotulo(modelo_82, "Escolha de ambiente (RF31): ",
        "contas com mais de um papel escolhem o ambiente ao entrar e podem trocá-lo pelo menu lateral."),
    bullet_com_rotulo(modelo_82, "Relatórios e backup (RF34, RF35): ",
        "indicadores do período com exportação em CSV e, para o superusuário, exportação e restauração dos "
        "dados em JSON."),
    bullet_com_rotulo(modelo_82, "Comunicados (RF28): ",
        "lista de avisos por aula, com publicação pelo Administrativo (qualquer aula) e pelo professor (as "
        "próprias aulas); o aluno vê os comunicados das aulas em que está matriculado."),
    bullet_com_rotulo(modelo_82, "Solicitações (RF29): ",
        "o aluno abre pedidos e acompanha a resposta; o Administrativo filtra por situação e responde."),
    bullet_com_rotulo(modelo_82, "Minha conta (RF30): ",
        "alteração da própria senha e alternância entre os temas claro e escuro, disponíveis a todos os perfis."),
    bullet_com_rotulo(modelo_82, "Aniversariantes do mês (RF26): ",
        "tela comum aos três perfis, com seletor de mês e quadro resumido no início de cada área; "
        "a idade a completar aparece apenas para o Administrativo e o Professor."),
    bullet_com_rotulo(modelo_82, "Portal do Aluno (RF25): ",
        "área com as aulas em que o aluno está matriculado, presenças e faltas, cobranças (situação "
        "informativa), comunicados recentes e histórico de matrículas, além da consulta da agenda da escola."),
])

# ======================================================================
# 8.3 Telas do protótipo (novas figuras)
# ======================================================================
TELAS = [
    ("Perfil Administrativo — acesso, cadastros e aulas", [
        ("00_login", "Tela de login, comum a todos os perfis (RF22)"),
        ("01_admin_inicio", "Painel inicial do perfil Administrativo, com o quadro de aniversariantes do mês (RF26)"),
        ("02_alunos_lista", "Consulta de alunos com busca por nome, e-mail ou telefone (RF02)"),
        ("03_aluno_cadastro", "Cadastro de aluno, com nome como único dado obrigatório (RF01)"),
        ("04_aluno_detalhe", "Detalhe do aluno: aulas, matrículas com mensalidade e desconto, cobranças e presenças (RF02, RF11, RF25)"),
        ("04b_matricula_desconto", "Mensalidade e desconto da matrícula, base das cobranças (RF11, RN18)"),
        ("04c_aluno_matriculas_encerradas", "Matrículas com ações de suspender/cancelar e matrículas encerradas com motivo (RF32, RN20)"),
        ("05_professores_lista", "Consulta de professores (RF17)"),
        ("06_professor_detalhe", "Detalhe do professor com salário estimado e acesso ao portal (RF13, RF17, RF25)"),
        ("07_modalidades_salas", "Manutenção de modalidades e salas (RF18)"),
        ("08_agenda_admin", "Agenda de aulas com filtros e lotação por sala; o Forró iniciante aparece na segunda e na quarta (RF05, RF19, RF20, RF36)"),
        ("09_agendar_aula_admin", "Agendamento de aula em um ou mais dias, com vigência e mensalidade da aula (RF19, RF11, RF36)"),
        ("10_turma_detalhe", "Detalhe da aula: alunos vinculados, vagas, registros e histórico de matrículas (RF20, RF21)"),
        ("11_vincular_alunos", "Vínculo de alunos à aula, limitado à capacidade da sala (RF20, RF21)"),
        ("12_chamada", "Chamada da aula por data, com inscritos e avulsos (RF03, RF04, RF33)"),
        ("12b_chamada_corrigida", "Chamada concluída aberta para correção pela administração, com motivo (RF33, RN19)"),
        ("12c_chamada_cancelada", "Aula cancelada na data, com motivo (RF33, RN19)"),
        ("13_presencas", "Consulta de presenças e faltas com filtros por aluno, aula, situação e período (RF04)"),
        ("29_aniversariantes", "Aniversariantes do mês vistos pelo Administrativo, com a idade a completar (RF26)"),
    ]),
    ("Perfil Administrativo — financeiro", [
        ("14_financeiro_painel", "Visão geral do financeiro (RF14, RF15)"),
        ("15_movimentacoes", "Consulta de movimentações com filtros por período, tipo e texto (RF14, RF23)"),
        ("16_nova_entrada", "Registro de entrada com origem e forma de pagamento separadas (RF06, RF08, RF10)"),
        ("17_nova_saida", "Registro de saída por categoria (RF07, RF09, RF10)"),
        ("18_correcao_lancamento", "Correção de lançamento financeiro (RF23)"),
        ("19_mensalidades", "Cobranças de mensalidade da competência: previsto, recebido, em aberto, saldo vencido e atalhos por situação (RF11, RN18)"),
        ("19c_mensalidades_atrasadas", "Mensalidades atrasadas de um período, abertas a partir do Relatório, com exportação em CSV (RF11, RF34)"),
        ("19b_cobranca", "Detalhe da cobrança: recebimento parcial, estorno com motivo e cancelamento (RF11, RF23, RN18)"),
        ("20_despesas", "Controle de despesas por categoria (RF12)"),
        ("21_salarios", "Cálculo do salário do professor por inscrições ativas no mês (RF13)"),
        ("22_saldo", "Saldo financeiro em regime de caixa (RF15)"),
        ("23_balanco", "Balanço financeiro mensal por origem, forma de pagamento e categoria (RF16)"),
        ("24_proprietario", "Visão do proprietário: resultado dos últimos seis meses (RF15, RF16)"),
    ]),
    ("Perfil Administrativo — comunicação, consultas e administração", [
        ("25_consultas", "Consulta de frequência e oportunidades: ocupação real, temperatura e tendência por aula (RF27)"),
        ("25b_relatorios", "Relatórios do período: quadro de mensalidades com links por situação e exportação em CSV (RF34)"),
        ("26b_comunicados_admin", "Comunicados publicados para as aulas (RF28)"),
        ("26c_solicitacoes_admin", "Solicitações dos alunos com filtro por situação (RF29)"),
        ("26d_solicitacao_responder", "Análise e resposta de uma solicitação (RF29)"),
        ("26_documentacao", "Documentação do projeto disponível no sistema"),
        ("27_administracao", "Acessos por papel, backup dos dados e trilha de auditoria (RF24, RF25, RF35)"),
        ("28_novo_acesso", "Criação de acesso com papel, vínculo ao cadastro e troca de senha no primeiro acesso (RF25, RF37)"),
        ("28d_papeis_conta", "Papéis de uma conta: professora que também é aluna (RF31)"),
        ("28b_trocar_senha", "Alteração da própria senha, disponível a todos os perfis (RF30)"),
        ("28c_modo_escuro", "Painel inicial no tema escuro (RF30, RNF06)"),
    ]),
    ("Perfil Professor", [
        ("30_prof_minha_area", "Portal do Professor: aulas, inscritos, salário estimado, comunicados e aniversariantes (RF13, RF25, RF26, RF28)"),
        ("31_prof_agenda", "Agenda vista pelo professor, com as próprias aulas destacadas (RF05, RF25)"),
        ("32_prof_agendar_aula", "Agendamento de aula pelo professor, sempre em seu nome (RF19, RF25)"),
        ("33_prof_chamada", "Chamada de uma aula do próprio professor (RF03, RF25)"),
        ("33b_prof_chamada_concluida", "Chamada concluída vista pelo professor, sem edição (RF33, RN19)"),
        ("34_prof_presencas", "Presenças e faltas restritas às aulas do professor (RF04, RF25)"),
        ("36_prof_meus_alunos", "Alunos das aulas do professor, com contato e frequência (RF38)"),
        ("35_prof_novo_comunicado", "Publicação de comunicado, limitada às aulas do professor (RF28)"),
    ]),
    ("Escolha de ambiente e primeiro acesso", [
        ("46_escolher_ambiente", "Escolha do ambiente por uma conta com os papéis Professor e Aluno (RF31)"),
        ("48_primeiro_acesso", "Primeiro acesso: troca da senha provisória antes de usar o sistema (RF37)"),
    ]),
    ("Perfil Aluno", [
        ("40_aluno_minha_area", "Portal do Aluno: aulas, presenças, situação financeira e cobranças (RF11, RF25)"),
        ("41_aluno_agenda", "Agenda vista pelo aluno, somente leitura, com as aulas matriculadas destacadas (RF05, RF25)"),
        ("41b_aluno_aniversariantes", "Aniversariantes do mês vistos pelo Aluno, somente dia e mês (RF26)"),
        ("43_aluno_comunicados", "Comunicados das aulas em que o aluno está matriculado (RF28)"),
        ("44_aluno_solicitacoes", "Solicitações do aluno e situação de cada uma (RF29)"),
        ("45_aluno_nova_solicitacao", "Abertura de solicitação pelo aluno (RF29)"),
        ("42_acesso_negado", "Acesso negado a uma página fora do papel do usuário (RF25, RN17, RNF03)"),
    ]),
]
fig_de = {}
xml_telas = [
    '<w:p><w:pPr><w:pStyle w:val="Ttulo2"/><w:keepNext/><w:spacing w:before="280" w:after="120"/></w:pPr>'
    '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/></w:rPr><w:t>8.3 Telas do protótipo</w:t></w:r></w:p>',
    par("As figuras a seguir apresentam cada tela do protótipo, capturadas no navegador com dados fictícios de "
        "demonstração (60 alunos, 4 professores, 10 aulas semanais e três meses de cobranças) e agrupadas pelo "
        "perfil de acesso, no visual baseado no protótipo v3. Todas "
        "as datas são exibidas e digitadas no padrão dd/mm/aaaa. A correspondência entre os requisitos e as "
        "figuras está na Tabela 5 (Seção 8.4)."),
]
for grupo, telas in TELAS:
    xml_telas.append(titulo3(grupo))
    for arq, desc in telas:
        n_fig += 1
        fig_de[arq] = n_fig
        xml_telas += [legenda(n_fig, desc), imagem(SHOTS / f"{arq}.png"), fonte()]

i = idx("8.3 Correspondência entre requisitos e protótipo")
vazio = i - 1
assert texto(blocos[vazio]).strip() == ""
blocos[vazio] = "".join(xml_telas)
blocos[i] = blocos[i].replace("8.3 Correspondência", "8.4 Correspondência")

# ======================================================================
# 8.4 Tabela 5
# ======================================================================
i = idx("A Tabela 5 relaciona todos os 24")
subst(i, "todos os 24 requisitos funcionais", "todos os 39 requisitos funcionais")
subst(i, "módulos/fluxos do protótipo", "módulos/fluxos e às figuras das telas do protótipo")
t5 = idx("RequisitoFuncionalidadeTela(s) do protótipo")
F = lambda *arqs: "Fig. " + ", ".join(str(n) for n in sorted(fig_de[a] for a in arqs))
TELAS_RF = {
    "RF01": F("03_aluno_cadastro"),
    "RF02": F("02_alunos_lista", "04_aluno_detalhe"),
    "RF03": F("12_chamada", "33_prof_chamada"),
    "RF04": F("12_chamada", "13_presencas", "34_prof_presencas"),
    "RF05": F("08_agenda_admin", "31_prof_agenda", "41_aluno_agenda"),
    "RF06": F("16_nova_entrada"),
    "RF07": F("17_nova_saida"),
    "RF08": F("16_nova_entrada"),
    "RF09": F("17_nova_saida"),
    "RF10": F("16_nova_entrada", "17_nova_saida"),
    "RF11": F("19_mensalidades", "19c_mensalidades_atrasadas", "19b_cobranca", "04_aluno_detalhe", "04b_matricula_desconto", "40_aluno_minha_area"),
    "RF12": F("20_despesas"),
    "RF13": F("21_salarios", "06_professor_detalhe", "30_prof_minha_area"),
    "RF14": F("14_financeiro_painel", "15_movimentacoes"),
    "RF15": F("22_saldo", "14_financeiro_painel", "24_proprietario"),
    "RF16": F("23_balanco", "24_proprietario"),
    "RF17": F("05_professores_lista", "06_professor_detalhe"),
    "RF18": F("07_modalidades_salas"),
    "RF19": F("09_agendar_aula_admin", "32_prof_agendar_aula"),
    "RF20": F("08_agenda_admin", "10_turma_detalhe", "11_vincular_alunos"),
    "RF21": F("11_vincular_alunos", "10_turma_detalhe"),
    "RF22": F("00_login"),
    "RF23": F("18_correcao_lancamento", "15_movimentacoes", "19b_cobranca"),
    "RF24": F("27_administracao"),
    "RF25": F("27_administracao", "28_novo_acesso", "30_prof_minha_area", "31_prof_agenda", "32_prof_agendar_aula",
              "33_prof_chamada", "34_prof_presencas", "40_aluno_minha_area", "41_aluno_agenda", "42_acesso_negado"),
    "RF26": F("29_aniversariantes", "41b_aluno_aniversariantes", "01_admin_inicio",
              "30_prof_minha_area"),
    "RF27": F("25_consultas"),
    "RF28": F("26b_comunicados_admin", "35_prof_novo_comunicado", "43_aluno_comunicados"),
    "RF29": F("26c_solicitacoes_admin", "26d_solicitacao_responder", "44_aluno_solicitacoes", "45_aluno_nova_solicitacao"),
    "RF30": F("28b_trocar_senha", "28c_modo_escuro"),
    "RF31": F("28d_papeis_conta", "46_escolher_ambiente"),
    "RF32": F("04c_aluno_matriculas_encerradas"),
    "RF33": F("12_chamada", "12b_chamada_corrigida", "12c_chamada_cancelada", "33b_prof_chamada_concluida"),
    "RF34": F("25b_relatorios", "19c_mensalidades_atrasadas"),
    "RF35": F("27_administracao"),
    "RF36": F("08_agenda_admin", "09_agendar_aula_admin"),
    "RF37": F("28_novo_acesso", "48_primeiro_acesso"),
    "RF38": F("36_prof_meus_alunos"),
    "RF39": "Comando de terminal (sem tela): portal.py usuarios",
}
tabela = blocos[t5]
linhas = re.findall(r"<w:tr[ >].*?</w:tr>", tabela, re.S)
modelo = [r for r in linhas if texto(r).startswith("RF23 —")][0]
nova = modelo
cel = re.findall(r"<w:tc>.*?</w:tc>", nova, re.S)
cel[0] = trocar_texto_paragrafo(cel[0], "RF25 — Controle de acesso por papéis")
cel[1] = trocar_texto_paragrafo(cel[1], "Papéis Administrativo, Professor e Aluno, portais e gestão de acessos "
                                       "(Módulos Acesso e Administração / Fluxos 00, 04, 05 e 06)")
nova = re.sub(r"<w:tc>.*?</w:tc>", lambda m, it=iter(cel): next(it), nova, flags=re.S)
modelo26 = [r for r in linhas if texto(r).startswith("RF24 —")][0]
nova += nova_linha(modelo26, ["RF26 — Aniversariantes do mês",
                              "Lista mensal de aniversariantes e quadro nos painéis iniciais (Módulo Alunos / Fluxo 22)", None])
nova += nova_linha(modelo, ["RF27 — Consulta de frequência e oportunidades",
                            "Ocupação real por aula, temperatura, tendência e promoções (Módulo Aulas / Fluxo 17)", None])
nova += nova_linha(modelo26, ["RF28 — Comunicados por aula",
                              "Publicação e consulta de avisos por aula, conforme o papel (Módulo Aulas / Fluxo 18)", None])
nova += nova_linha(modelo, ["RF29 — Solicitações dos alunos",
                            "Pedidos do aluno e resposta da administração (Módulo Alunos / Fluxo 19)", None])
nova += nova_linha(modelo26, ["RF30 — Preferências da conta",
                              "Alteração da própria senha e tema claro/escuro (Módulo Acesso / Fluxo 25)", None])
for k, (cod, nome, func) in enumerate([
        ("RF31", "Vários papéis na mesma conta", "Escolha e troca de ambiente (Módulo Acesso / Fluxo 00)"),
        ("RF32", "Suspensão e cancelamento de matrícula", "Encerramento com motivo e reativação (Módulo Aulas / Fluxo 05)"),
        ("RF33", "Situação da chamada", "Chamada concluída, cancelada e correção justificada (Módulo Aulas / Fluxo 06)"),
        ("RF34", "Relatórios do período", "Indicadores, mensalidades por situação e CSV (Módulo Administração / Fluxo 20)"),
        ("RF35", "Backup dos dados", "Exportação e restauração em JSON (Módulo Administração / Fluxo 21)"),
        ("RF36", "Aulas em vários dias e vigência", "Agendamento em vários dias com vigência (Módulo Aulas / Fluxo 04)"),
        ("RF37", "Troca de senha no primeiro acesso", "Senha provisória com troca obrigatória (Módulo Acesso / Fluxos 00 e 25)"),
        ("RF38", "Alunos do professor", "Lista de alunos das próprias aulas (Módulo Professores / Fluxo 23)"),
        ("RF39", "Criação dos usuários padrão", "Comando de administração para os acessos padrão (Módulo Acesso / Fluxo 24)")]):
    nova += nova_linha(modelo if k % 2 == 0 else modelo26, [f"{cod} — {nome}", func, None])
tabela = tabela.replace("</w:tbl>", nova + "</w:tbl>")
VAZIA = '<w:sz w:val="19"/></w:rPr></w:r></w:p></w:tc></w:tr>'
for linha in re.findall(r"<w:tr[ >].*?</w:tr>", tabela, re.S):
    cod = texto(linha)[:4]
    if cod in TELAS_RF:
        assert linha.endswith(VAZIA), cod
        nova_l = linha[:-len(VAZIA)] + f'<w:sz w:val="19"/></w:rPr><w:t>{escape(TELAS_RF[cod])}</w:t></w:r></w:p></w:tc></w:tr>'
        tabela = tabela.replace(linha, nova_l, 1)
tabela = tabela.replace(escape("RF18 — Cadastro e manutenção de aulas"),
                        escape("RF18 — Cadastro e manutenção de modalidades e salas"))
tabela = tabela.replace(escape("Registro e consulta informativa de mensalidades (Módulo Financeiro / Fluxo 10)"),
                        escape("Cobranças mensais, recebimentos, estornos e situação informativa (Módulo Financeiro / Fluxo 10)"))
tabela = tabela.replace(escape("(Módulo Financeiro / Fluxo 15)"), escape("(Módulo Financeiro / Fluxos 10 e 15)"))
tabela = tabela.replace(escape("(Módulo Administração / Fluxos 00, 05, 15 e 16)"), escape("(Módulo Administração / Fluxos 00, 05, 15, 16 e 21)"))
blocos[t5] = tabela

# ======================================================================
# 9, 10, 11
# ======================================================================
i = idx("Segurança e rastreabilidade:")
subst(i, "por meio de autenticação obrigatória e registro de auditoria alinhado à LGPD.",
      "por meio de autenticação obrigatória, controle de acesso por papéis — cada usuário vê apenas as "
      "informações da sua função — e registro de auditoria alinhado à LGPD.")
i = idx("Confirmação de parâmetros com a empresa parceira:")
subst(i, "(RF22–RF24 e RN13–RN16).", "(RF22–RF39 e RN13–RN20), incluindo o escopo de cada papel de acesso, a política de cobranças e as regras de chamada e matrícula.")
i = idx("Como possibilidades de evolução")
subst(i, "(ii) evolução do módulo financeiro para contemplar emissão de cobranças/parcelamentos e estornos contábeis vinculados ao lançamento original (em substituição à exclusão direta);",
      "(ii) integração das cobranças a meios de pagamento online (Pix com QR Code e boleto) e envio de "
      "lembretes de vencimento aos alunos;")
subst(i, "(iii) eventual criação de perfis de consulta individual para professores (visualização da própria agenda e remuneração) e alunos (consulta de horários e mensalidades), caso a escola deseje expandir o acesso;",
      "(iii) ampliação do autoatendimento nos portais do professor e do aluno (por exemplo, recuperação de "
      "senha por e-mail e atualização cadastral pelo próprio aluno);")
i = idx("A coerência do projeto é assegurada")
subst(i, "nos 24 requisitos funcionais, 8 requisitos não funcionais e 16 regras de negócio",
      "nos 39 requisitos funcionais, 8 requisitos não funcionais e 20 regras de negócio")
subst(i, "detalhados nos fluxogramas das operações principais",
      "detalhados nos 26 fluxogramas das operações do sistema")

# ======================================================================
# Apêndices A e B: documentos da empresa (versão sem assinatura física)
# ======================================================================
def nota_apendice(texto):
    return ('<w:p><w:pPr><w:spacing w:before="80" w:after="120"/><w:jc w:val="center"/></w:pPr>'
            '<w:r><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:i/><w:color w:val="555555"/>'
            f'<w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">{escape(texto)}</w:t></w:r></w:p>')


# Versão pública (repositório): sem --apendices os apêndices ficam vazios (LGPD).
for prefixo, arquivo, nome in [] if not ARGS.apendices else [
        ("APÊNDICE A", "ap_autorizacao", "Autorização Institucional"),
        ("APÊNDICE B", "ap_declaracao", "Declaração de Conclusão do Projeto")]:
    i = idx(prefixo)
    vazio = i + 1
    assert texto(blocos[vazio]).strip() == ""
    blocos[vazio] = (imagem(ARGS.apendices / f"{arquivo}.png", largura_emu=5000000)
                     + nota_apendice(f"{nome} emitida pela Portal da Dança LTDA (CNPJ 39.415.463/0001-50). "
                                     "Versão incluída sem assinatura física."))

# ======================================================================
# Listas: cada grupo de itens recomeça em 1
# ======================================================================
numeracao = (W / "numbering.xml").read_text(encoding="utf-8")
prox_num = max(int(x) for x in re.findall(r'<w:num w:numId="(\d+)"', numeracao)) + 1
novos_nums = []
# Re-separa os blocos em parágrafos/tabelas individuais (alguns trechos novos
# foram inseridos como vários parágrafos num só bloco) e numera cada item.
corpo = "".join(blocos)
blocos = [m.group(0) for m in re.finditer(r"<w:(p|tbl)[ >].*?</w:\1>", corpo, re.S)]
assert "".join(blocos) == corpo
anterior_lista = False
num_atual = None
for k, b in enumerate(blocos):
    eh_lista = b.startswith("<w:p") and '<w:pStyle w:val="Commarcadores"/>' in b[:400]
    if eh_lista:
        if not anterior_lista:
            num_atual = prox_num
            prox_num += 1
            novos_nums.append(f'<w:num w:numId="{num_atual}"><w:abstractNumId w:val="0"/>'
                              '<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>')
        b = re.sub(r"<w:numPr>.*?</w:numPr>", "", b, count=1, flags=re.S)
        # Itens de lista alinhados à esquerda: o justificado esticava os espaços
        # entre as palavras nos itens com rótulo em negrito (ex.: 8.2, itens 2 e 13).
        b = b.replace('<w:jc w:val="both"/>', '<w:jc w:val="left"/>', 1)
        blocos[k] = b.replace('<w:pStyle w:val="Commarcadores"/>',
                              f'<w:pStyle w:val="Commarcadores"/><w:numPr><w:ilvl w:val="0"/>'
                              f'<w:numId w:val="{num_atual}"/></w:numPr>', 1)
    anterior_lista = eh_lista
numeracao = numeracao.replace("</w:numbering>", "".join(novos_nums) + "</w:numbering>")
(W / "numbering.xml").write_text(numeracao, encoding="utf-8")

# ---------------------------------------------------------------- gravar
doc = doc[:ini] + "".join(blocos) + doc[fim:]
(W / "document.xml").write_text(doc, encoding="utf-8")
rels = rels.replace("</Relationships>", "".join(novas_rels) + "</Relationships>")
rels_path.write_text(rels, encoding="utf-8")
rodape = (W / "footer1.xml").read_text(encoding="utf-8")
assert "Modelo de relatório de proposta" in rodape
rodape = rodape.replace("Modelo de relatório de proposta", "Relatório técnico — Portal da Dança")
(W / "footer1.xml").write_text(rodape, encoding="utf-8")

# ---------------------------------------------------------------- empacotar e converter
destino = (ARGS.apendices if ARGS.apendices else AQUI).resolve()
docx = destino / f"{NOME}.docx"
docx.unlink(missing_ok=True)
subprocess.run(["zip", "-qXr", str(docx), "."], cwd=BASE, check=True)
subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(destino), str(docx)],
               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
shutil.rmtree(TMP)
print("figuras:", n_fig, "| listas:", len(novos_nums))
print("gerado:", docx, "e", docx.with_suffix(".pdf"))
