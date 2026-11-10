from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def brl(valor):
    """Formata um número como moeda brasileira: 1234.5 -> R$ 1.234,50."""
    try:
        valor = Decimal(valor or 0)
    except (InvalidOperation, TypeError, ValueError):
        return valor
    sinal = "-" if valor < 0 else ""
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {texto}"
