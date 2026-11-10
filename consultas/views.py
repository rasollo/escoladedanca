from django.shortcuts import render

from .services import PERIODO_PADRAO, PERIODOS, consulta


def index(request):
    """Consulta: aulas mais frequentadas e oportunidades de promoção."""
    try:
        semanas = int(request.GET.get("semanas", PERIODO_PADRAO))
    except ValueError:
        semanas = PERIODO_PADRAO
    if semanas not in PERIODOS:
        semanas = PERIODO_PADRAO
    return render(request, "consultas/index.html", consulta(semanas))
