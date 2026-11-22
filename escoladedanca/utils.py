from datetime import datetime

from django import forms
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


# ---------------------------------------------------------------------------
# Datas no padrão brasileiro (dd/mm/aaaa) em todos os formulários
# ---------------------------------------------------------------------------
FORMATO_DATA = "%d/%m/%Y"


class DataBR(forms.DateInput):
    """Campo de data sempre em dd/mm/aaaa, independente do idioma do navegador.

    O DateField do Django continua aceitando também AAAA-MM-DD (links antigos).
    """

    def __init__(self, attrs=None):
        padrao = {"placeholder": "dd/mm/aaaa", "inputmode": "numeric", "maxlength": "10",
                  "pattern": r"\d{2}/\d{2}/\d{4}", "autocomplete": "off",
                  "title": "Data no formato dd/mm/aaaa"}
        super().__init__(attrs={**padrao, **(attrs or {})}, format=FORMATO_DATA)


def ler_data(texto):
    """Converte 'dd/mm/aaaa' (ou 'aaaa-mm-dd') em date; vazio → None.

    Lança ValueError se a data for inválida.
    """
    texto = (texto or "").strip()
    if not texto:
        return None
    for formato in (FORMATO_DATA, "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError(f"Data inválida: {texto}")


ATTRS_MES = {"placeholder": "mm/aaaa", "inputmode": "numeric", "maxlength": "7",
             "pattern": r"\d{2}/\d{4}", "autocomplete": "off", "title": "Mês no formato mm/aaaa"}


def ler_mes(texto):
    """Converte 'mm/aaaa' (ou 'aaaa-mm') em (ano, mês). Lança ValueError se inválido."""
    texto = (texto or "").strip()
    if "/" in texto:
        mes, ano = (int(p) for p in texto.split("/"))
    else:
        ano, mes = (int(p) for p in texto.split("-"))
    if not (1 <= mes <= 12 and 1900 <= ano <= 9999):
        raise ValueError(f"Mês inválido: {texto}")
    return ano, mes


def validar_nascimento(data):
    """Data de nascimento é opcional, mas não pode estar no futuro."""
    from django.utils import timezone
    if data and data > timezone.localdate():
        raise forms.ValidationError("A data de nascimento não pode estar no futuro.")
    return data
