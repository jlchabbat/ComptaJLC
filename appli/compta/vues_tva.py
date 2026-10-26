"""Page TVA : déclaration d'une période et liquidation."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

from . import tva


def _periode(donnees):
    """Période demandée (AAAA-MM-JJ), sinon le mois précédent."""
    try:
        return dt.date.fromisoformat(donnees["debut"]), dt.date.fromisoformat(donnees["fin"])
    except (KeyError, ValueError):
        fin = dt.date.today().replace(day=1) - dt.timedelta(days=1)
        return fin.replace(day=1), fin


@login_required
@permission_required("compta.view_mouvement", raise_exception=True)
def page(request):
    debut, fin = _periode(request.POST if request.method == "POST" else request.GET)
    if request.method == "POST":
        if not request.user.has_perm("compta.add_mouvement"):
            messages.error(request, "Droits insuffisants pour passer l'écriture.")
        elif debut > fin:
            messages.error(request, "La période commence après sa fin.")
        else:
            try:
                mv = tva.liquider(debut, fin, request.user)
                messages.success(request, f"Liquidation passée : Mvt {mv.numero}.")
            except ValueError as e:
                messages.error(request, str(e))
        return redirect(f"{request.path}?debut={debut:%Y-%m-%d}&fin={fin:%Y-%m-%d}")
    return render(request, "compta/tva.html", {"d": tva.declaration(debut, fin)})
