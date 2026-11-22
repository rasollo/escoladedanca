from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from alunos.models import Aluno
from escoladedanca.rbac import (ADMINISTRATIVO, ALUNO, PROFESSOR, aluno_do, exigir_turma_propria, papel_do,
                                permitir, professor_do)
from escoladedanca.utils import ler_data, redirecionar

from .forms import (ChamadaForm, EncerrarMatriculaForm, FiltroAgendaForm,
                    MatriculaFinanceiroForm, ModalidadeForm,
                    SalaForm, TurmaForm, TurmaProfessorForm, VinculoAlunosForm)
from .models import (Chamada, Matricula, Modalidade, Presenca, Sala, Turma,
                     pode_editar_chamada)


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
    dia_filtro = None
    if form.is_valid():
        dia_filtro = form.cleaned_data.get("dia")
        if form.cleaned_data.get("modalidade"):
            turmas = turmas.filter(modalidade=form.cleaned_data["modalidade"])
        if form.cleaned_data.get("sala"):
            turmas = turmas.filter(sala=form.cleaned_data["sala"])
    turmas = list(turmas)
    if dia_filtro is not None:
        turmas = [t for t in turmas if t.acontece_em(dia_filtro)]
    # Uma aula com vários dias aparece em cada um deles.
    dias = []
    for valor, rotulo in Turma.DiaSemana.choices:
        if dia_filtro is not None and valor != dia_filtro:
            continue
        do_dia = sorted((t for t in turmas if t.acontece_em(valor)),
                        key=lambda t: (t.hora_inicio, t.sala.nome))
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


def matricula_editar(request, pk):
    """Mensalidade e desconto da matrícula (somente Administrativo)."""
    matricula = get_object_or_404(Matricula.objects.select_related("aluno", "turma"), pk=pk)
    form = MatriculaFinanceiroForm(request.POST or None, instance=matricula)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mensalidade da matrícula atualizada. Vale para as próximas cobranças.")
        return redirect(matricula.aluno)
    return render(request, "form.html", {
        "form": form, "titulo": f"Mensalidade de {matricula.aluno} em {matricula.turma}",
        "secao": "Matrícula", "voltar": matricula.aluno.get_absolute_url(),
    })


@require_POST
def matricula_encerrar(request, pk):
    """Suspende ou cancela a matrícula com motivo (o histórico é preservado)."""
    m = get_object_or_404(Matricula.objects.select_related("aluno", "turma"), pk=pk,
                          data_fim__isnull=True)
    form = EncerrarMatriculaForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Escolha suspender ou cancelar e informe o motivo.")
        return redirect(m.aluno)
    with transaction.atomic():
        m.turma.alunos.remove(m.aluno)  # encerra a matrícula (data de fim = hoje)
        Matricula.objects.filter(pk=m.pk).update(situacao=form.cleaned_data["situacao"],
                                                 motivo=form.cleaned_data["motivo"])
    rotulo = "suspensa" if form.cleaned_data["situacao"] == Matricula.Situacao.SUSPENSA else "cancelada"
    messages.success(request, f"Matrícula em {m.turma} {rotulo}. Não entra nas próximas cobranças.")
    return redirect(m.aluno)


@require_POST
def matricula_reativar(request, pk):
    """Reativa uma matrícula suspensa: nova matrícula a partir de hoje, mesma mensalidade."""
    m = get_object_or_404(Matricula.objects.select_related("aluno", "turma__sala"), pk=pk,
                          situacao=Matricula.Situacao.SUSPENSA)
    turma = m.turma
    if turma.alunos.filter(pk=m.aluno_id).exists():
        messages.warning(request, "O aluno já está matriculado nesta aula.")
        return redirect(m.aluno)
    if not turma.ativa:
        messages.error(request, "A aula está desativada.")
        return redirect(m.aluno)
    try:
        turma.validar_quantidade(turma.quantidade_alunos() + 1)  # RN09 — lotação
    except ValidationError as erro:
        messages.error(request, erro.messages[0])
        return redirect(m.aluno)
    with transaction.atomic():
        turma.alunos.add(m.aluno)
        Matricula.objects.filter(turma=turma, aluno=m.aluno, data_fim__isnull=True).update(
            valor_mensal=m.valor_mensal, desconto_tipo=m.desconto_tipo, desconto=m.desconto)
    messages.success(request, f"Matrícula em {turma} reativada.")
    return redirect(m.aluno)


# ---------------------------------------------------------------------------
# RF03 / RF04 — chamada (fluxo 06)
# ---------------------------------------------------------------------------
def _ultima_ocorrencia(turma, ref):
    """Data mais recente (até ref) em que a aula acontece."""
    for atras in range(0, 7 * 60):
        d = ref - timedelta(days=atras)
        if turma.data_valida(d):
            return d
    return ref


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

    papel = papel_do(request.user)
    registro_chamada = Chamada.objects.filter(turma=turma, data=data).first()
    situacao = registro_chamada.situacao if registro_chamada else Chamada.Situacao.ABERTA
    voltar = f"{reverse('aulas:chamada', args=[turma.pk])}?data={data:%d/%m/%Y}"

    if request.method == "POST":
        acao = request.POST.get("acao", "salvar")
        motivo = " ".join(request.POST.get("motivo", "").split())[:200]
        if acao in ("reabrir", "cancelar"):
            if acao == "reabrir":
                if papel != ADMINISTRATIVO or not registro_chamada:
                    raise PermissionDenied("Somente a administração reabre uma chamada.")
                registro_chamada.situacao = Chamada.Situacao.ABERTA
                registro_chamada.atualizado_por = request.user
                registro_chamada.save()
                messages.success(request, "Chamada reaberta.")
            elif situacao != Chamada.Situacao.ABERTA or registros:
                messages.error(request, "Só é possível cancelar a aula com a chamada aberta e sem registros.")
            elif not motivo:
                messages.error(request, "Informe o motivo do cancelamento da aula.")
            else:
                Chamada.objects.update_or_create(turma=turma, data=data, defaults={
                    "situacao": Chamada.Situacao.CANCELADA, "motivo": motivo,
                    "atualizado_por": request.user})
                messages.success(request, f"Aula de {data:%d/%m/%Y} cancelada: {motivo}.")
            return redirect(voltar)
        if not pode_editar_chamada(papel, situacao):
            messages.error(request, "Esta chamada está concluída ou cancelada. Correções são feitas "
                                    "pela administração, com motivo.")
            return redirect(voltar)
        correcao = situacao == Chamada.Situacao.CONCLUIDA  # só a administração chega aqui
        if correcao and not motivo:
            messages.error(request, "Informe o motivo da correção de uma chamada concluída.")
            return redirect(voltar)
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
                nova_situacao = (Chamada.Situacao.CONCLUIDA if acao == "concluir" or correcao
                                 else Chamada.Situacao.ABERTA)
                Chamada.objects.update_or_create(turma=turma, data=data, defaults={
                    "situacao": nova_situacao, "atualizado_por": request.user,
                    **({"motivo": f"Correção: {motivo}"} if correcao else {}),
                })
            partes = [f"Chamada de {data:%d/%m/%Y} {'corrigida' if correcao else 'concluída' if acao == 'concluir' else 'salva'}"]
            if novos_avulsos:
                partes.append(f"{len(novos_avulsos)} avulso{'s' if len(novos_avulsos) > 1 else ''} "
                              f"incluído{'s' if len(novos_avulsos) > 1 else ''}")
            if remover:
                partes.append(f"{len(remover)} removido{'s' if len(remover) > 1 else ''} da chamada")
            messages.success(request, ", ".join(partes) + ".")
        return redirect(voltar)

    ids_lista = [a.pk for a in lista]
    return render(request, "aulas/chamada.html", {
        "turma": turma, "form": form, "data": data,
        "linhas": [{"aluno": a, "registro": registros.get(a.pk),
                    "vinculado": a in vinculados} for a in lista],
        "candidatos_avulsos": Aluno.objects.filter(ativo=True).exclude(pk__in=ids_lista),
        "presentes": sum(1 for p in registros.values() if p.presente),
        "faltas": sum(1 for p in registros.values() if not p.presente),
        "registro_chamada": registro_chamada, "situacao": situacao,
        "pode_editar": pode_editar_chamada(papel, situacao),
        "correcao": situacao == Chamada.Situacao.CONCLUIDA and papel == ADMINISTRATIVO,
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
