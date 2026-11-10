from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from alunos.models import Aluno
from aulas.models import Presenca, Turma
from financeiro.services import balanco_mensal, calcular_saldo
from professores.models import Professor


def index(request):
    """Painel inicial do responsável pela Portal da Dança."""
    hoje = timezone.localdate()
    aulas_hoje = (
        Turma.objects.filter(ativa=True, dia_semana=hoje.weekday())
        .select_related("modalidade", "sala", "professor")
        .annotate(qtd_alunos=Count("alunos"))
    )
    return render(request, "template/index.html", {
        "total_alunos": Aluno.objects.filter(ativo=True).count(),
        "total_professores": Professor.objects.filter(ativo=True).count(),
        "total_turmas": Turma.objects.filter(ativa=True).count(),
        "presencas_mes": Presenca.objects.filter(
            presente=True, data__year=hoje.year, data__month=hoje.month
        ).count(),
        "aulas_hoje": aulas_hoje,
        "saldo": calcular_saldo(),
        "balanco": balanco_mensal(hoje.year, hoje.month),
        "hoje": hoje,
    })


# ---------------------------------------------------------------------------
# Documentação do projeto (docs/*.md) — visível apenas para usuários logados
# ---------------------------------------------------------------------------
from django.conf import settings
from django.http import Http404
from django.utils.safestring import mark_safe

from .markdown_simples import converter

# Lista fechada de documentos: o slug da URL nunca vira caminho de arquivo.
DOCUMENTOS = {
    "resumo": ("Resumo da revisão", "RESUMO.md"),
    "analise": ("Análise e rastreabilidade", "ANALISE.md"),
}


def documentacao(request, slug="resumo"):
    if slug not in DOCUMENTOS:
        raise Http404("Documento não encontrado.")
    titulo, arquivo = DOCUMENTOS[slug]
    caminho = settings.BASE_DIR / "docs" / arquivo
    try:
        conteudo = caminho.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise Http404("Documento não encontrado.")
    return render(request, "documentacao.html", {
        "titulo": titulo,
        "slug": slug,
        "documentos": [(s, t) for s, (t, _) in DOCUMENTOS.items()],
        "html": mark_safe(converter(conteudo)),  # converter() escapa todo o texto
    })
