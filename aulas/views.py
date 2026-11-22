from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from alunos.models import Aluno
from escoladedanca.rbac import (ALUNO, PROFESSOR, aluno_do, exigir_turma_propria, papel_do,
                                permitir, professor_do)
from escoladedanca.utils import ler_data, redirecionar

from .forms import (ChamadaForm, FiltroAgendaForm, ModalidadeForm, SalaForm, TurmaForm,
                    TurmaProfessorForm, VinculoAlunosForm)
from .models import Modalidade, Presenca, Sala, Turma


# ---------------------------------------------------------------------------
# Helpers genéricos de CRUD
# ---------------------------------------------------------------------------
def _form_view(request, form_class, titulo, voltar, instance=None, sucesso="Salvo.",
               **form_kwargs):
    form = form_class(request.POST or None, instance=instance, **form_kwargs)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        messages.success(request, sucesso)
        destino = obj.get_absolute_url() if hasattr(obj, "get_absolute_url") else voltar
        return redirecionar(request, destino)
    return render(request, "form.html", {
        "form": form, "titulo": titulo, "secao": "Aulas", "voltar": voltar,
    })


def _excluir_view(request, obj, voltar, sucesso):
    if request.method == "POST":
        try:
            obj.delete()
        except ProtectedError:
            messages.error(
                request,
                f"“{obj}” possui registros vinculados e não pode ser removido. "
                "Para aulas com histórico de presença, desmarque “ativa” em Editar.",
            )
            return redirect(voltar)
        messages.success(request, sucesso)
        return redirect(voltar)
    return render(request, "confirmar_exclusao.html", {"objeto": obj, "voltar": voltar})


def _professor_logado(request):
    """Cadastro do professor logado; sem vínculo, o acesso é negado."""
    professor = professor_do(request.user)
    if professor is None:
        raise PermissionDenied("Seu usuário não está vinculado a um professor ativo.")
    return professor


def _turma_form(request):
    """Administrativo escolhe o professor; o professor agenda só para si (RF25)."""
    if papel_do(request.user) == PROFESSOR:
        return TurmaProfessorForm, {"professor": _professor_logado(request)}
    return TurmaForm, {}


# ---------------------------------------------------------------------------
# RF05 / RF19 — agenda de aulas (fluxos 04 e 14)
# ---------------------------------------------------------------------------
@permitir(PROFESSOR, ALUNO)
def agenda(request):
    form = FiltroAgendaForm(request.GET or None)
    turmas = (
        Turma.objects.filter(ativa=True)
        .select_related("modalidade", "sala", "professor")
        .annotate(qtd_alunos=Count("alunos", distinct=True))
    )
    if form.is_valid():
        if form.cleaned_data.get("dia") is not None:
            turmas = turmas.filter(dia_semana=form.cleaned_data["dia"])
        if form.cleaned_data.get("modalidade"):
            turmas = turmas.filter(modalidade=form.cleaned_data["modalidade"])
        if form.cleaned_data.get("sala"):
            turmas = turmas.filter(sala=form.cleaned_data["sala"])
    dias = []
    for valor, rotulo in Turma.DiaSemana.choices:
        do_dia = [t for t in turmas if t.dia_semana == valor]
        if do_dia:
            dias.append({"rotulo": rotulo, "turmas": do_dia})
    # Aulas do próprio usuário: destacadas na agenda (professor: as que dá;
    # aluno: as que está matriculado).
    papel = papel_do(request.user)
    minhas = set()
    if papel == PROFESSOR:
        minhas = set(Turma.objects.filter(professor__usuario=request.user)
                     .values_list("pk", flat=True))
    elif papel == ALUNO:
        aluno = aluno_do(request.user)
        if aluno:
            minhas = set(aluno.turmas.values_list("pk", flat=True))
    return render(request, "aulas/agenda.html", {
        "form": form, "dias": dias, "total": len(turmas),
        "inativas": Turma.objects.filter(ativa=False).count(),
        "minhas": minhas,
    })


@permitir(PROFESSOR)
def turma_detalhe(request, pk):
    turma = get_object_or_404(
        Turma.objects.select_related("modalidade", "sala", "professor"), pk=pk
    )
    exigir_turma_propria(request, turma)
    return render(request, "aulas/turma_detalhe.html", {
        "turma": turma,
        "alunos": turma.alunos.all(),
        "ultimas_presencas": turma.presencas.select_related("aluno")[:20],
        "matriculas": turma.matriculas.select_related("aluno")[:40],
    })


@permitir(PROFESSOR)
def turma_nova(request):
    form_class, extra = _turma_form(request)
    return _form_view(request, form_class, "Agendar aula", reverse("aulas:agenda"),
                      sucesso="Aula agendada.", **extra)


@permitir(PROFESSOR)
def turma_editar(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    exigir_turma_propria(request, turma)
    form_class, extra = _turma_form(request)
    return _form_view(request, form_class, "Editar aula agendada", turma.get_absolute_url(),
                      instance=turma, sucesso="Aula atualizada.", **extra)


def turma_excluir(request, pk):
    turma = get_object_or_404(Turma, pk=pk)
    return _excluir_view(request, turma, reverse("aulas:agenda"), "Aula removida.")


@permitir(PROFESSOR)
def turma_alunos(request, pk):
    """RF20 / RF21 — vincular ou atualizar os alunos da aula."""
    turma = get_object_or_404(Turma.objects.select_related("sala"), pk=pk)
    exigir_turma_propria(request, turma)
    form = VinculoAlunosForm(request.POST or None, turma=turma)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Alunos vinculados atualizados.")
        return redirect(turma)
    return render(request, "aulas/turma_alunos.html", {"turma": turma, "form": form})


# ---------------------------------------------------------------------------
# RF03 / RF04 — chamada (fluxo 06)
# ---------------------------------------------------------------------------
def _ultima_ocorrencia(turma, ref):
    return ref - timedelta(days=(ref.weekday() - turma.dia_semana) % 7)


@permitir(PROFESSOR)
def chamada(request, pk):
    turma = get_object_or_404(Turma.objects.select_related("sala", "modalidade"), pk=pk)
    exigir_turma_propria(request, turma)
    dados = request.POST if request.method == "POST" else request.GET
    if "data" not in dados:
        dados = {"data": f"{_ultima_ocorrencia(turma, timezone.localdate()):%d/%m/%Y}"}
    form = ChamadaForm(dados, turma=turma)
    if not form.is_valid():
        return render(request, "aulas/chamada.html", {"turma": turma, "form": form})
    data = form.cleaned_data["data"]

    registros = {p.aluno_id: p for p in turma.presencas.filter(data=data).select_related("aluno")}
    vinculados = list(turma.alunos.filter(ativo=True))
    avulsos = [p.aluno for aid, p in registros.items() if aid not in {a.pk for a in vinculados}]
    lista = vinculados + sorted(avulsos, key=lambda a: a.nome)

    if request.method == "POST":
        ids_vinculados = {a.pk for a in vinculados}
        # Avulso salvo por engano: o operador pode tirá-lo da chamada (não vira falta).
        remover = {a.pk for a in avulsos if request.POST.get(f"remover_{a.pk}")}
        marcacoes = {}
        for aluno in lista:
            if aluno.pk in remover:
                continue
            valor = request.POST.get(f"aluno_{aluno.pk}")
            if valor in ("P", "F"):
                marcacoes[aluno.pk] = valor == "P"
        # RN08: um ou mais alunos avulsos (sem matrícula) podem participar da aula.
        # Ignora vazios, repetidos, inativos e quem já está na lista desta aula.
        pedidos = {int(v) for v in request.POST.getlist("avulso") if v.isdigit()}
        pedidos -= {a.pk for a in lista}
        novos_avulsos = set(
            Aluno.objects.filter(pk__in=pedidos, ativo=True).values_list("pk", flat=True)
        )
        for aluno_id in novos_avulsos:
            marcacoes[aluno_id] = True

        # Capacidade conferida sobre o resultado final da chamada.
        final = {aid: p.presente for aid, p in registros.items() if aid not in remover}
        final.update(marcacoes)
        try:
            turma.validar_quantidade(sum(final.values()))
        except ValidationError as erro:
            messages.error(request, erro.messages[0])
        else:
            with transaction.atomic():
                if remover:
                    turma.presencas.filter(data=data, aluno_id__in=remover).exclude(
                        aluno_id__in=ids_vinculados).delete()
                for aluno_id, presente in marcacoes.items():
                    Presenca.objects.update_or_create(
                        turma=turma, aluno_id=aluno_id, data=data,
                        defaults={"presente": presente},
                    )
            partes = [f"Chamada de {data:%d/%m/%Y} salva"]
            if novos_avulsos:
                partes.append(f"{len(novos_avulsos)} avulso{'s' if len(novos_avulsos) > 1 else ''} "
                              f"incluído{'s' if len(novos_avulsos) > 1 else ''}")
            if remover:
                partes.append(f"{len(remover)} removido{'s' if len(remover) > 1 else ''} da chamada")
            messages.success(request, ", ".join(partes) + ".")
        return redirect(f"{reverse('aulas:chamada', args=[turma.pk])}?data={data:%d/%m/%Y}")

    ids_lista = [a.pk for a in lista]
    return render(request, "aulas/chamada.html", {
        "turma": turma, "form": form, "data": data,
        "linhas": [{"aluno": a, "registro": registros.get(a.pk),
                    "vinculado": a in vinculados} for a in lista],
        "candidatos_avulsos": Aluno.objects.filter(ativo=True).exclude(pk__in=ids_lista),
        "presentes": sum(1 for p in registros.values() if p.presente),
        "faltas": sum(1 for p in registros.values() if not p.presente),
    })


@permitir(PROFESSOR)
def presencas(request):
    """RF04 — consulta de presenças e faltas (fim do fluxo 06).

    O professor vê apenas as presenças das próprias aulas (RF25 / LGPD).
    """
    qs = Presenca.objects.select_related("aluno", "turma__modalidade", "turma__sala")
    turmas = Turma.objects.select_related("modalidade", "sala")
    alunos = Aluno.objects.all()
    if papel_do(request.user) == PROFESSOR:
        professor = _professor_logado(request)
        qs = qs.filter(turma__professor=professor)
        turmas = turmas.filter(professor=professor)
        alunos = alunos.filter(
            Q(presencas__turma__professor=professor) | Q(turmas__professor=professor)
        ).distinct()
    filtros = {
        "aluno": request.GET.get("aluno", ""),
        "turma": request.GET.get("turma", ""),
        "status": request.GET.get("status", ""),
        "inicio": request.GET.get("inicio", ""),
        "fim": request.GET.get("fim", ""),
    }
    if filtros["aluno"].isdigit():
        qs = qs.filter(aluno_id=filtros["aluno"])
    if filtros["turma"].isdigit():
        qs = qs.filter(turma_id=filtros["turma"])
    if filtros["status"] == "presente":
        qs = qs.filter(presente=True)
    elif filtros["status"] == "falta":
        qs = qs.filter(presente=False)
    try:
        inicio, fim = ler_data(filtros["inicio"]), ler_data(filtros["fim"])
        if inicio:
            qs = qs.filter(data__gte=inicio)
        if fim:
            qs = qs.filter(data__lte=fim)
        total_presencas = qs.filter(presente=True).count()
    except (ValueError, ValidationError):
        messages.error(request, "Data inválida no filtro.")
        qs = qs.none()
        total_presencas = 0
    return render(request, "aulas/presencas.html", {
        "pagina": Paginator(qs, 30).get_page(request.GET.get("page")),
        "filtros": filtros,
        "alunos": alunos,
        "turmas": turmas,
        "total_presencas": total_presencas,
        "total_faltas": qs.count() - total_presencas,
    })


# ---------------------------------------------------------------------------
# RF18 — modalidades e salas (fluxo 03)
# ---------------------------------------------------------------------------
def modalidades(request):
    return render(request, "aulas/modalidades.html", {
        "modalidades": Modalidade.objects.annotate(qtd_turmas=Count("turmas")),
        "salas": Sala.objects.annotate(qtd_turmas=Count("turmas")),
    })


def modalidade_nova(request):
    return _form_view(request, ModalidadeForm, "Nova modalidade",
                      reverse("aulas:modalidades"), sucesso="Modalidade cadastrada.")


def modalidade_editar(request, pk):
    obj = get_object_or_404(Modalidade, pk=pk)
    return _form_view(request, ModalidadeForm, "Editar modalidade",
                      reverse("aulas:modalidades"), instance=obj,
                      sucesso="Modalidade atualizada.")


def modalidade_excluir(request, pk):
    obj = get_object_or_404(Modalidade, pk=pk)
    return _excluir_view(request, obj, reverse("aulas:modalidades"), "Modalidade removida.")


def sala_nova(request):
    return _form_view(request, SalaForm, "Nova sala", reverse("aulas:modalidades"),
                      sucesso="Sala cadastrada.")


def sala_editar(request, pk):
    obj = get_object_or_404(Sala, pk=pk)
    return _form_view(request, SalaForm, "Editar sala", reverse("aulas:modalidades"),
                      instance=obj, sucesso="Sala atualizada.")
