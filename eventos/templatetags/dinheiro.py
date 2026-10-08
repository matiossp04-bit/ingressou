from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def dinheiro(valor):
    """Formata Decimal como moeda brasileira: 1234.5 -> '1.234,50'."""
    try:
        valor = Decimal(valor)
    except Exception:
        return valor
    texto = f"{valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")
