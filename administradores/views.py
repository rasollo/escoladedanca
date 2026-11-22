from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from escoladedanca.auditoria import ler_eventos, log_dados, registrar, resumo_acessos
from escoladedanca.rbac import ADMINISTRATIVO, papeis_do, remover_papel

from .forms import NovoUsuarioForm, PapelExtraForm


def index(request):
    """Administração do acesso (RF25 / RNF03) e trilha de auditoria (RNF04 — LGPD)."""
    usuarios = list(get_user_model().objects.order_by("username")
                    .select_related("professor", "aluno").prefetch_related("groups"))
    for u in usuarios:
        u.papel = " + ".join(papeis_do(u)) if u.is_active else _papel_inativo(u)
        u.vinculo = getattr(u, "professor", None) or getattr(u, "aluno", None)
    contexto = {"usuarios": usuarios}
    # IPs e histórico de acesso também são dados pessoais: só a equipe técnica vê.
    if request.user.is_staff:
        desde = datetime.now() - timedelta(days=30)
        contexto["resumo"] = resumo_acessos(desde)
        contexto["eventos"] = list(reversed(ler_eventos(
            "acessos.log", desde, {"LOGIN_OK", "LOGIN_FALHOU", "LOGOUT"})))[:30]
        contexto["alteracoes"] = list(reversed(ler_eventos("auditoria.log", desde)))[:30]
    return render(request, "administradores/index.html", contexto)


def _papel_inativo(user):
    """Papel de um usuário bloqueado (papel_do devolve None para inativos)."""
    if user.is_superuser:
        return "Administrativo"
    return next((g.name for g in user.groups.all()), None)


def usuario_novo(request):
    """RF25 — cria o acesso de um administrativo, professor ou aluno."""
    inicial = {}
    for campo in ("papel", "professor", "aluno"):
        if request.GET.get(campo):
            inicial[campo] = request.GET[campo]
    form = NovoUsuarioForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Acesso “{user.username}” criado com o papel "
                                  f"{form.cleaned_data['papel']}.")
        return redirect("administradores:administradores")
    return render(request, "form.html", {
        "form": form, "titulo": "Novo acesso ao sistema", "secao": "Administração",
        "voltar": "/administradores/",
    })


@require_POST
def usuario_situacao(request, pk):
    """Bloqueia ou desbloqueia um acesso (sem apagar o histórico de auditoria)."""
    user = get_object_or_404(get_user_model(), pk=pk)
    if user == request.user:
        messages.error(request, "Você não pode bloquear o próprio acesso.")
    elif user.is_superuser and not request.user.is_superuser:
        messages.error(request, "Somente um superusuário pode bloquear outro superusuário.")
    else:
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
        messages.success(request, f"Acesso “{user.username}” "
                                  f"{'desbloqueado' if user.is_active else 'bloqueado'}.")
    return redirect("administradores:administradores")


def usuario_papeis(request, pk):
    """Papéis de uma conta: acrescentar (com vínculo ao cadastro) ou remover."""
    user = get_object_or_404(get_user_model(), pk=pk)
    form = PapelExtraForm(request.POST or None, usuario=user)
    if request.method == "POST":
        if "remover" in request.POST:
            papel = request.POST["remover"]
            atuais = papeis_do(user)
            if papel not in atuais or len(atuais) == 1:
                messages.error(request, "A conta precisa manter ao menos um papel.")
            elif user == request.user and papel == ADMINISTRATIVO:
                messages.error(request, "Você não pode remover o próprio papel Administrativo.")
            elif user.is_superuser and papel == ADMINISTRATIVO:
                messages.error(request, "Superusuários são sempre administrativos.")
            else:
                remover_papel(user, papel)
                messages.success(request, f"Papel {papel} removido de {user.username}.")
            return redirect("administradores:usuario_papeis", user.pk)
        if form.is_valid():
            papel = form.save()
            messages.success(request, f"Papel {papel} acrescentado. Ao entrar, {user.username} "
                                      "escolhe o ambiente.")
            return redirect("administradores:usuario_papeis", user.pk)
    return render(request, "administradores/papeis.html", {
        "u": user, "papeis": papeis_do(user), "form": form,
        "vinculo_professor": getattr(user, "professor", None) if hasattr(user, "professor") else None,
        "vinculo_aluno": getattr(user, "aluno", None) if hasattr(user, "aluno") else None,
    })


def _exigir_superusuario(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Backup e restauração são exclusivos do superusuário.")


def backup_exportar(request):
    """Baixa todos os dados do sistema em JSON (dados pessoais: guarde com cuidado)."""
    from .backup import exportar
    _exigir_superusuario(request)
    resp = HttpResponse(exportar(), content_type="application/json; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="portal-da-danca-{timezone.localdate():%Y%m%d}.json"'
    registrar(log_dados, "BACKUP_EXPORTADO", usuario=request.user.username)
    return resp


@require_POST
def backup_restaurar(request):
    from .backup import restaurar
    _exigir_superusuario(request)
    arquivo = request.FILES.get("arquivo")
    if request.POST.get("confirmacao", "").strip().upper() != "RESTAURAR":
        messages.error(request, "Digite RESTAURAR para confirmar a substituição dos dados.")
    elif not arquivo or arquivo.size > 50 * 1024 * 1024:
        messages.error(request, "Envie o arquivo .json exportado pelo sistema (até 50 MB).")
    else:
        try:
            n = restaurar(arquivo.read().decode("utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as erro:
            messages.error(request, f"Restauração cancelada: {erro}")
        except Exception as erro:  # noqa: BLE001 — qualquer falha desfaz a transação inteira
            messages.error(request, f"Restauração cancelada; nada foi alterado ({type(erro).__name__}).")
        else:
            registrar(log_dados, "BACKUP_RESTAURADO", usuario=request.user.username, registros=n)
            messages.success(request, f"Backup restaurado: {n} registros. Entre novamente.")
            return redirect("login")
    return redirect("administradores:administradores")
