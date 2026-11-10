from django.shortcuts import render
from django.utils import timezone

from financeiro.services import balanco_mensal, calcular_saldo


def index(request):
    """Visão do proprietário: resultado dos últimos 6 meses (RF15 / RF16)."""
    hoje = timezone.localdate()
    meses = []
    ano, mes = hoje.year, hoje.month
    for _ in range(6):
        meses.append(balanco_mensal(ano, mes))
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return render(request, "proprietarios/index.html", {
        "saldo": calcular_saldo(), "meses": meses,
    })
