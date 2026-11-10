"""Conversor Markdown → HTML mínimo, sem dependências, para a página Documentação.

Suporta: títulos (#, ##, ###), parágrafos, listas com aninhamento (- item),
tabelas no formato GFM, blocos de código (```), `código`, **negrito**, *itálico*
e [links](url). Todo o texto é escapado antes da formatação (sem HTML bruto).
"""
import html
import re

_INLINE = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*(.+?)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])"), r"<em>\1</em>"),
]
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def _inline(texto: str) -> str:
    texto = html.escape(texto, quote=True)
    # protege o conteúdo de `código` contra as demais regras
    codigos = []

    def guardar(m):
        codigos.append(m.group(1))
        return f"\x00{len(codigos) - 1}\x00"

    texto = re.sub(r"`([^`]+)`", guardar, texto)
    for padrao, troca in _INLINE[1:]:
        texto = padrao.sub(troca, texto)

    def link(m):
        url = m.group(2)
        if not re.match(r"^(https?://|/|#)", url):
            return m.group(1)
        return f'<a href="{url}">{m.group(1)}</a>'

    texto = _LINK.sub(link, texto)
    return re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codigos[int(m.group(1))]}</code>", texto)


def _celulas(linha: str) -> list[str]:
    return [c.strip() for c in linha.strip().strip("|").split("|")]


def _eh_separador(linha: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*", linha))


def converter(md: str) -> str:
    linhas = md.replace("\r\n", "\n").split("\n")
    saida, i = [], 0
    while i < len(linhas):
        linha = linhas[i]

        if linha.startswith("```"):
            bloco, i = [], i + 1
            while i < len(linhas) and not linhas[i].startswith("```"):
                bloco.append(linhas[i])
                i += 1
            saida.append(f"<pre><code>{html.escape(chr(10).join(bloco))}</code></pre>")
            i += 1
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", linha)
        if m:
            n = len(m.group(1))
            saida.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            i += 1
            continue

        if linha.lstrip().startswith("|") and i + 1 < len(linhas) and _eh_separador(linhas[i + 1]):
            cab = "".join(f"<th>{_inline(c)}</th>" for c in _celulas(linha))
            corpo, i = [], i + 2
            while i < len(linhas) and linhas[i].lstrip().startswith("|"):
                corpo.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in _celulas(linhas[i])) + "</tr>")
                i += 1
            saida.append(f'<div class="table-wrap"><table><thead><tr>{cab}</tr></thead>'
                         f'<tbody>{"".join(corpo)}</tbody></table></div>')
            continue

        if re.match(r"^\s*[-*]\s+", linha):
            pilha = []  # indentações abertas
            while i < len(linhas) and re.match(r"^\s*[-*]\s+", linhas[i]):
                m = re.match(r"^(\s*)[-*]\s+(.*)$", linhas[i])
                nivel = len(m.group(1))
                if not pilha or nivel > pilha[-1]:
                    saida.append("<ul>")
                    pilha.append(nivel)
                else:
                    while pilha and nivel < pilha[-1]:
                        saida.append("</li></ul>")
                        pilha.pop()
                    saida.append("</li>")
                saida.append(f"<li>{_inline(m.group(2))}")
                i += 1
            saida.append("</li></ul>" * len(pilha))
            continue

        if not linha.strip():
            i += 1
            continue

        paragrafo = []
        while (i < len(linhas) and linhas[i].strip() and not linhas[i].startswith(("#", "```", "|"))
               and not re.match(r"^\s*[-*]\s+", linhas[i])):
            paragrafo.append(linhas[i].strip())
            i += 1
        saida.append(f"<p>{_inline(' '.join(paragrafo))}</p>")
    return "\n".join(saida)
