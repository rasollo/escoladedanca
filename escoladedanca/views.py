from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils import timezone

from alunos.models import Aluno
from aulas.models import Presenca, Turma
from financeiro.services import balanco_mensal, calcular_saldo
from professores.models import Professor

from .aniversarios import MESES, aniversariantes_do_mes, ve_idade
from .aniversarios import aniversariantes as lista_aniversariantes
from .rbac import (ADMINISTRATIVO, ALUNO, PAPEIS, PROFESSOR, SESSAO_PAPEL, aluno_do, papel_do,
                   papeis_do, permitir, professor_do, qualquer_usuario)


@permitir(*PAPEIS)
def index(request):
    """Painel inicial: cada papel cai na sua própria área (RF25)."""
    papel = papel_do(request.user)
    if papel == PROFESSOR:
        return redirect("professores:minha_area")
    if papel == ALUNO:
        return redirect("alunos:minha_area")
    hoje = timezone.localdate()
    aulas_hoje = sorted(
        (t for t in Turma.objects.filter(ativa=True)
         .select_related("modalidade", "sala", "professor")
         .annotate(qtd_alunos=Count("alunos"))
         if t.data_valida(hoje)),
        key=lambda t: t.hora_inicio,
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
        "aniversariantes": aniversariantes_do_mes(request.user, hoje),
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


RELATORIO_PDF = "Relatorio_Portal_da_Danca_v2.0.pdf"
FLUXOGRAMAS_PDF = "Portal_da_Danca_Fluxogramas_v2.0.pdf"


def _pdf(pasta, arquivo, erro):
    from django.http import FileResponse
    caminho = settings.BASE_DIR / "docs" / pasta / arquivo
    if not caminho.exists():
        raise Http404(erro)
    return FileResponse(open(caminho, "rb"), content_type="application/pdf",
                        filename=arquivo, as_attachment=False)


def relatorio_pdf(request):
    """Relatório final do projeto (PDF), para quem tem acesso à Documentação."""
    return _pdf("relatorio", RELATORIO_PDF, "Relatório não encontrado.")


def fluxogramas_pdf(request):
    """Fluxogramas do sistema (PDF, versão 2.0), para quem tem acesso à Documentação."""
    return _pdf("fluxogramas", FLUXOGRAMAS_PDF, "Fluxogramas não encontrados.")


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


# ---------------------------------------------------------------------------
# RF26 — aniversariantes do mês (todos os papéis)
# ---------------------------------------------------------------------------


@permitir(*PAPEIS)
def aniversariantes(request):
    hoje = timezone.localdate()
    try:
        mes = int(request.GET.get("mes", hoje.month))
    except ValueError:
        mes = hoje.month
    if not 1 <= mes <= 12:
        mes = hoje.month
    anterior, proximo = (mes - 2) % 12 + 1, mes % 12 + 1
    return render(request, "aniversariantes.html", {
        "lista": lista_aniversariantes(mes, hoje, com_idade=ve_idade(request.user)),
        "mes": mes, "mes_nome": MESES[mes - 1],
        "meses": list(enumerate(MESES, start=1)),
        "anterior": (anterior, MESES[anterior - 1]), "proximo": (proximo, MESES[proximo - 1]),
    })


# ---------------------------------------------------------------------------
# Alterar a própria senha (todos os papéis)
# ---------------------------------------------------------------------------


@qualquer_usuario
def trocar_senha(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # mantém a sessão aberta
        from administradores.models import marcar_troca_de_senha
        marcar_troca_de_senha(user, False)
        messages.success(request, "Senha alterada.")
        return redirect("index")
    return render(request, "form.html", {
        "form": form, "titulo": "Alterar minha senha", "secao": "Minha conta", "voltar": "/",
    })


# ---------------------------------------------------------------------------
# Escolha do ambiente (conta com mais de um papel)
# ---------------------------------------------------------------------------


@qualquer_usuario
def ambiente(request):
    papeis = papeis_do(request.user)
    if request.method == "POST":
        escolhido = request.POST.get("papel")
        if escolhido in papeis:
            request.session[SESSAO_PAPEL] = escolhido
            messages.success(request, f"Ambiente {escolhido} ativo.")
            return redirect("index")
        messages.error(request, "Escolha um dos seus ambientes.")
    if len(papeis) <= 1 and request.method == "GET":
        return redirect("index")
    descricao = {
        ADMINISTRATIVO: ("Gestão escolar", "Cadastros, aulas, financeiro e acessos."),
        PROFESSOR: (getattr(professor_do(request.user), "nome", "Professor"),
                    "Suas aulas, chamadas e comunicados."),
        ALUNO: (getattr(aluno_do(request.user), "nome", "Aluno"),
                "Suas aulas, presenças, mensalidades e solicitações."),
    }
    return render(request, "ambiente.html", {
        "opcoes": [{"papel": p, "nome": descricao[p][0], "texto": descricao[p][1]} for p in papeis],
        "atual": request.session.get(SESSAO_PAPEL),
    })
