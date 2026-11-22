from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from escoladedanca.aniversarios import aniversariantes_do_mes
from escoladedanca.rbac import ALUNO, aluno_do, permitir

from .forms import AlunoForm
from .models import Aluno


def lista(request):
    """RF02 — consulta dos alunos cadastrados (fluxo 01, ramo Consultar)."""
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "ativos")
    alunos = Aluno.objects.prefetch_related("turmas")
    if status == "ativos":
        alunos = alunos.filter(ativo=True)
    elif status == "inativos":
        alunos = alunos.filter(ativo=False)
    if q:
        alunos = alunos.filter(Q(nome__icontains=q) | Q(email__icontains=q) | Q(telefone__icontains=q))
    return render(request, "alunos/lista.html", {
        "pagina": Paginator(alunos, 30).get_page(request.GET.get("page")),
        "q": q, "status": status, "total": alunos.count(),
        "total_ativos": Aluno.objects.filter(ativo=True).count(),
    })


def novo(request):
    """RF01 — cadastro de aluno (fluxo 01, ramo Cadastrar)."""
    form = AlunoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        aluno = form.save()
        messages.success(request, f"Aluno {aluno.nome} cadastrado.")
        return redirect(aluno)
    return render(request, "form.html", {
        "form": form, "titulo": "Cadastrar aluno", "secao": "Alunos", "voltar": "/alunos/",
    })


def detalhe(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    return render(request, "alunos/detalhe.html", {
        "aluno": aluno,
        "turmas": aluno.turmas.select_related("modalidade", "sala", "professor"),
        "presencas": aluno.presencas.select_related("turma__modalidade")[:20],
        "mensalidades": aluno.movimentacoes.filter(origem="mensalidade")[:12],
        "em_dia": aluno.mensalidade_em_dia(),
    })


def editar(request, pk):
    aluno = get_object_or_404(Aluno, pk=pk)
    form = AlunoForm(request.POST or None, instance=aluno)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dados do aluno atualizados.")
        return redirect(aluno)
    return render(request, "form.html", {
        "form": form, "titulo": f"Editar {aluno.nome}", "secao": "Alunos",
        "voltar": aluno.get_absolute_url(),
    })


@permitir(ALUNO)
def minha_area(request):
    """RF25 — portal do aluno: aulas matriculadas, presenças e mensalidades.

    O aluno vê somente os próprios dados (LGPD). A situação da mensalidade é
    informativa, como no restante do sistema (RN08).
    """
    aluno = aluno_do(request.user)
    if aluno is None:
        raise PermissionDenied("Seu usuário ainda não está vinculado a um cadastro de aluno.")
    return render(request, "alunos/minha_area.html", {
        "aluno": aluno,
        "turmas": aluno.turmas.filter(ativa=True).select_related("modalidade", "sala", "professor"),
        "matriculas": aluno.matriculas.select_related("turma__modalidade")[:20],
        "presencas": aluno.presencas.select_related("turma__modalidade", "turma__sala")[:30],
        "mensalidades": aluno.movimentacoes.filter(origem="mensalidade")[:12],
        "em_dia": aluno.mensalidade_em_dia(),
        "aniversariantes": aniversariantes_do_mes(request.user),
    })
