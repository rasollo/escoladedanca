from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.shortcuts import render

from escoladedanca.auditoria import ler_eventos, resumo_acessos


def index(request):
    """Administração do acesso (RNF03) e trilha de auditoria (RNF04 — LGPD)."""
    contexto = {"usuarios": get_user_model().objects.order_by("username")}
    # IPs e histórico de acesso também são dados pessoais: só a equipe vê.
    if request.user.is_staff:
        desde = datetime.now() - timedelta(days=30)
        contexto["resumo"] = resumo_acessos(desde)
        contexto["eventos"] = list(reversed(ler_eventos(
            "acessos.log", desde, {"LOGIN_OK", "LOGIN_FALHOU", "LOGOUT"})))[:30]
        contexto["alteracoes"] = list(reversed(ler_eventos("auditoria.log", desde)))[:30]
    return render(request, "administradores/index.html", contexto)
