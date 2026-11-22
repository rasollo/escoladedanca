from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from aulas.models import Turma
from escoladedanca.rbac import (ADMINISTRATIVO, ALUNO, PROFESSOR, aluno_do, papel_do,
                                permitir)

from .forms import ComunicadoForm, RespostaForm, SolicitacaoForm, turmas_que_pode_comunicar
from .models import Comunicado, Solicitacao


def comunicados_visiveis(user):
    """Administração: todos; professor: das próprias aulas; aluno: das aulas matriculadas."""
    papel = papel_do(user)
    qs = Comunicado.objects.select_related("turma__modalidade", "autor")
    if papel == ADMINISTRATIVO:
        return qs
    if papel == PROFESSOR:
        return qs.filter(turma__professor__usuario=user)
    aluno = aluno_do(user)
    if aluno is None:
        return qs.none()
    return qs.filter(turma__matriculas__aluno=aluno,
                     turma__matriculas__data_fim__isnull=True).distinct()


@permitir(PROFESSOR, ALUNO)
def comunicados(request):
    papel = papel_do(request.user)
    return render(request, "comunicacao/comunicados.html", {
        "comunicados": comunicados_visiveis(request.user)[:50],
        "pode_publicar": papel in (ADMINISTRATIVO, PROFESSOR),
    })


@permitir(PROFESSOR)
def comunicado_novo(request):
    turmas = turmas_que_pode_comunicar(papel_do(request.user), request.user)
    if not turmas.exists():
        raise PermissionDenied("Você não tem aulas ativas para publicar comunicados.")
    inicial = {}
    if request.GET.get("turma", "").isdigit():
        inicial["turma"] = request.GET["turma"]
    form = ComunicadoForm(request.POST or None, turmas=turmas, initial=inicial)
    if request.method == "POST" and form.is_valid():
        comunicado = form.save(commit=False)
        comunicado.autor = request.user
        comunicado.save()
        messages.success(request, "Comunicado publicado para a turma.")
        return redirect("comunicacao:comunicados")
    return render(request, "form.html", {
        "form": form, "titulo": "Novo comunicado", "secao": "Comunicados",
        "voltar": "/comunicacao/comunicados/",
    })


@permitir(ALUNO)
def solicitacoes(request):
    """Aluno: as próprias; administração: todas, com filtro por situação."""
    papel = papel_do(request.user)
    qs = Solicitacao.objects.select_related("aluno", "respondido_por")
    status = request.GET.get("status", "")
    if papel == ALUNO:
        aluno = aluno_do(request.user)
        if aluno is None:
            raise PermissionDenied("Seu usuário ainda não está vinculado a um cadastro de aluno.")
        qs = qs.filter(aluno=aluno)
    elif status in Solicitacao.Status.values:
        qs = qs.filter(status=status)
    return render(request, "comunicacao/solicitacoes.html", {
        "solicitacoes": qs[:100], "status": status, "status_choices": Solicitacao.Status.choices,
        "abertas": Solicitacao.objects.filter(
            status__in=[Solicitacao.Status.PENDENTE, Solicitacao.Status.EM_ANALISE]).count()
        if papel == ADMINISTRATIVO else None,
    })


@permitir(ALUNO)
def solicitacao_nova(request):
    aluno = aluno_do(request.user)
    if aluno is None or papel_do(request.user) != ALUNO:
        raise PermissionDenied("Somente alunos abrem solicitações.")
    form = SolicitacaoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        s = form.save(commit=False)
        s.aluno = aluno
        s.save()
        messages.success(request, "Solicitação enviada. Acompanhe a resposta por aqui.")
        return redirect("comunicacao:solicitacoes")
    return render(request, "form.html", {
        "form": form, "titulo": "Nova solicitação", "secao": "Solicitações",
        "voltar": "/comunicacao/solicitacoes/",
    })


def solicitacao_responder(request, pk):
    """Administração analisa a solicitação (somente Administrativo)."""
    s = get_object_or_404(Solicitacao.objects.select_related("aluno"), pk=pk)
    form = RespostaForm(request.POST or None, instance=s)
    if request.method == "POST" and form.is_valid():
        resposta = form.save(commit=False)
        resposta.respondido_por = request.user
        resposta.save()
        messages.success(request, "Solicitação atualizada.")
        return redirect("comunicacao:solicitacoes")
    return render(request, "comunicacao/responder.html", {"s": s, "form": form})
