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


@register.filter
def get_item(dictionnaire, cle):
    """Valeur d'un dictionnaire dans un gabarit : {{ d|get_item:cle }}."""
    return dictionnaire.get(cle) if dictionnaire else None


@register.simple_tag(takes_context=True)
def bouton_retour(context, fiche=None, defaut=None, texte="← Retour à la liste"):
    """Bouton de retour à la liste d'où la fiche a été ouverte (filtres compris) ; voir compta/retour.py."""
    from django.utils.html import format_html
    from ..retour import adresse
    return format_html('<a class="bouton" href="{}">{}</a>', adresse(context["request"], fiche, defaut), texte)
