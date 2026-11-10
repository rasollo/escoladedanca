from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

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
