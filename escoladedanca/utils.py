from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


def redirecionar(request, padrao):
    """Redireciona para ?next= somente se for uma URL interna (evita open redirect)."""
    destino = request.POST.get("next") or request.GET.get("next")
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(destino)
    return redirect(padrao)
