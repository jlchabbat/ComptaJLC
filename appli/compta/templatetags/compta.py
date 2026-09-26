from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def shekel(v, signe=""):
    """1234.5 → « 1 234,50 » (espace fine insécable pour les milliers)."""
    if v in (None, ""):
        return ""
    v = Decimal(v)
    texte = f"{abs(v):,.2f}".replace(",", " ").replace(".", ",")
    return ("−" if v < 0 else "") + texte


@register.filter
def zero_vide(v):
    return "" if v in (None, "", 0) else shekel(v)


@register.filter
def sub(a, b):
    return Decimal(a or 0) - Decimal(b or 0)
