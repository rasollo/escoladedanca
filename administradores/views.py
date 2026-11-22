from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from escoladedanca.auditoria import ler_eventos, resumo_acessos
from escoladedanca.rbac import papel_do

from .forms import NovoUsuarioForm


def index(request):
    """Administração do acesso (RF25 / RNF03) e trilha de auditoria (RNF04 — LGPD)."""
    usuarios = list(get_user_model().objects.order_by("username")
                    .select_related("professor", "aluno").prefetch_related("groups"))
    for u in usuarios:
        u.papel = papel_do(u) if u.is_active else _papel_inativo(u)
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
