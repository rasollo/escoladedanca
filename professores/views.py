from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comunicacao.views import comunicados_visiveis
from escoladedanca.aniversarios import aniversariantes_do_mes
from escoladedanca.rbac import PROFESSOR, permitir, professor_do
from financeiro.services import calcular_salario

from .forms import ProfessorForm
from .models import Professor


def lista(request):
    """RF17 — consulta de professores (fluxo 02)."""
    q = request.GET.get("q", "").strip()
    professores = Professor.objects.annotate(
        qtd_turmas=Count("turmas", filter=Q(turmas__ativa=True))
    )
    if q:
        professores = professores.filter(nome__icontains=q)
    return render(request, "professores/lista.html", {"professores": professores, "q": q})


def novo(request):
    form = ProfessorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        professor = form.save()
        messages.success(request, f"Professor {professor.nome} cadastrado.")
        return redirect(professor)
    return render(request, "form.html", {
        "form": form, "titulo": "Cadastrar professor", "secao": "Professores",
        "voltar": "/professores/",
    })


def detalhe(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    hoje = timezone.localdate()
    return render(request, "professores/detalhe.html", {
        "professor": professor,
        "turmas": professor.turmas.select_related("modalidade", "sala"),
        "calculo": calcular_salario(professor, hoje.year, hoje.month),
        "pagamentos": professor.pagamentos.all()[:12],
    })


def editar(request, pk):
    professor = get_object_or_404(Professor, pk=pk)
    form = ProfessorForm(request.POST or None, instance=professor)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dados do professor atualizados.")
        return redirect(professor)
    return render(request, "form.html", {
        "form": form, "titulo": f"Editar {professor.nome}", "secao": "Professores",
        "voltar": professor.get_absolute_url(),
    })


@permitir(PROFESSOR)
def minha_area(request):
    """RF25 — portal do professor: próprias aulas, inscritos e salário estimado."""
    professor = professor_do(request.user)
    if professor is None:
        raise PermissionDenied("Seu usuário ainda não está vinculado a um professor ativo.")
    hoje = timezone.localdate()
    turmas = (professor.turmas.filter(ativa=True).select_related("modalidade", "sala")
              .annotate(qtd_alunos=Count("alunos", distinct=True)))
    return render(request, "professores/minha_area.html", {
        "professor": professor,
        "turmas": turmas,
        "aulas_hoje": [t for t in turmas if t.data_valida(hoje)],
        "calculo": calcular_salario(professor, hoje.year, hoje.month),
        "pagamentos": professor.pagamentos.all()[:6],
        "hoje": hoje,
        "aniversariantes": aniversariantes_do_mes(request.user, hoje),
        "comunicados": comunicados_visiveis(request.user)[:3],
    })


@permitir(PROFESSOR)
def meus_alunos(request):
    """Alunos matriculados nas aulas do professor, com contato e frequência nelas."""
    from alunos.models import Aluno
    from aulas.models import Presenca
    professor = professor_do(request.user)
    if professor is None:
        raise PermissionDenied("Seu usuário ainda não está vinculado a um professor ativo.")
    turmas = list(professor.turmas.filter(ativa=True).select_related("modalidade"))
    q = request.GET.get("q", "").strip()
    alunos = (Aluno.objects.filter(turmas__in=turmas, ativo=True).distinct()
              .prefetch_related("turmas"))
    if q:
        alunos = alunos.filter(nome__icontains=q)
    linhas = []
    for a in alunos:
        regs = Presenca.objects.filter(aluno=a, turma__professor=professor)
        total = regs.count()
        presentes = regs.filter(presente=True).count()
        linhas.append({"aluno": a, "aulas": [t for t in a.turmas.all() if t.professor_id == professor.pk],
                       "frequencia": round(100 * presentes / total) if total else None})
    return render(request, "professores/meus_alunos.html", {"linhas": linhas, "q": q,
                                                              "total": len(linhas)})
