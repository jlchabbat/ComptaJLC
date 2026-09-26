"""Pages de consultation : tableau de bord, écritures, grand livre, balance, analytique, contrôles."""

import datetime as dt

from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Case, F, Q, Sum, Value, When
from django.shortcuts import get_object_or_404, render

from . import controles as ctrl
from .models import ZERO, arrondi, CodeAnalytique, Compte, Exercice, Journal, Ligne, Modification, Mouvement, soldes

consulter = permission_required("compta.view_mouvement", raise_exception=True)


def periode(request):
    """Période choisie (?du=AAAA-MM-JJ&au=…), par défaut l'exercice ouvert."""
    ex = Exercice.ouvert()
    def lire(cle, defaut):
        try:
            return dt.date.fromisoformat(request.GET.get(cle, ""))
        except ValueError:
            return defaut
    debut = lire("du", ex.debut if ex else dt.date(2000, 1, 1))
    fin = lire("au", ex.fin if ex else dt.date(2100, 12, 31))
    return debut, fin


def lignes_periode(debut, fin):
    return Ligne.objects.filter(mouvement__date__range=(debut, fin))


def resultat_par_axe(lignes, axe):
    """Produits (7), charges (6) et résultat par code d'axe 1 ou 2, en une requête."""
    champ = "compte__anal1" if axe == 1 else "anal2"
    classe7 = Q(compte__numero__startswith="7")
    classe6 = Q(compte__numero__startswith="6")
    rows = (lignes.filter(classe6 | classe7).values(champ, f"{champ}__libelle").order_by(champ)
            .annotate(produits=Sum(Case(When(classe7, then=F("credit") - F("debit")), default=Value(ZERO))),
                      charges=Sum(Case(When(classe6, then=F("debit") - F("credit")), default=Value(ZERO)))))
    return [{"code": r[champ], "libelle": r[f"{champ}__libelle"], "produits": arrondi(r["produits"]),
             "charges": arrondi(r["charges"]), "resultat": arrondi(r["produits"] - r["charges"])} for r in rows]


@login_required
@consulter
def tableau_de_bord(request):
    debut, fin = periode(request)
    ls = lignes_periode(debut, fin)
    _, _, charges = soldes(ls.filter(compte__numero__startswith="6"))
    _, _, produits = soldes(ls.filter(compte__numero__startswith="7"))
    tresorerie = []
    for j in Journal.objects.filter(compte__isnull=False).select_related("compte"):
        _, _, s = soldes(Ligne.objects.filter(compte=j.compte, mouvement__date__lte=fin))
        tresorerie.append({"journal": j, "solde": s})
    res = ctrl.executer()
    etat, a_verifier = ctrl.etat_general(res)
    return render(request, "compta/tableau_de_bord.html", {
        "debut": debut, "fin": fin, "produits": -produits, "charges": charges, "resultat": -(produits + charges),
        "tresorerie": tresorerie, "total_tresorerie": sum((t["solde"] for t in tresorerie), ZERO),
        "axe1": resultat_par_axe(ls, 1), "axe2": resultat_par_axe(ls, 2), "etat": etat, "a_verifier": a_verifier,
        "nb_mouvements": Mouvement.objects.filter(date__range=(debut, fin)).count(),
    })


@login_required
@consulter
def ecritures(request):
    debut, fin = periode(request)
    qs = (lignes_periode(debut, fin).select_related("mouvement", "mouvement__journal", "compte", "compte__anal1", "anal2")
          .order_by("-mouvement__date", "-mouvement__numero", "ordre"))
    f = {k: request.GET.get(k, "").strip() for k in ("journal", "compte", "anal2", "q")}
    if f["journal"]:
        qs = qs.filter(mouvement__journal_id=f["journal"])
    if f["compte"]:
        qs = qs.filter(compte__numero__startswith=f["compte"])
    if f["anal2"]:
        qs = qs.filter(anal2_id=f["anal2"])
    if f["q"]:
        qs = qs.filter(Q(libelle__icontains=f["q"]) | Q(compte__libelle__icontains=f["q"]))
    d, c, _ = soldes(qs)
    page = Paginator(qs, 100).get_page(request.GET.get("page"))
    return render(request, "compta/ecritures.html", {
        "page": page, "filtres": f, "debut": debut, "fin": fin, "total_debit": d, "total_credit": c,
        "journaux": Journal.objects.all(), "codes2": CodeAnalytique.objects.filter(axe=2),
    })


@login_required
@consulter
def mouvement(request, numero):
    m = get_object_or_404(Mouvement.objects.select_related("journal"), numero=numero)
    return render(request, "compta/mouvement.html", {"m": m, "lignes": m.lignes.select_related("compte", "anal2")})


@login_required
@consulter
def grand_livre(request):
    debut, fin = periode(request)
    numero = request.GET.get("compte", "")
    compte = Compte.objects.filter(numero=numero).first()
    lignes, ouverture = [], ZERO
    if compte:
        _, _, ouverture = soldes(Ligne.objects.filter(compte=compte, mouvement__date__lt=debut))
        cumul = ouverture
        for l in (Ligne.objects.filter(compte=compte, mouvement__date__range=(debut, fin))
                  .select_related("mouvement", "anal2").order_by("mouvement__date", "mouvement__numero", "ordre")):
            cumul += l.debit - l.credit
            lignes.append((l, cumul))
    return render(request, "compta/grand_livre.html", {
        "comptes": Compte.objects.all(), "compte": compte, "lignes": lignes, "ouverture": ouverture,
        "debut": debut, "fin": fin, "cloture": lignes[-1][1] if lignes else ouverture,
    })


@login_required
@consulter
def balance(request):
    debut, fin = periode(request)
    rows = (lignes_periode(debut, fin).values("compte__numero", "compte__libelle")
            .annotate(d=Sum("debit"), c=Sum("credit")).order_by("compte__numero"))
    lignes = [{"numero": r["compte__numero"], "libelle": r["compte__libelle"], "debit": arrondi(r["d"]),
               "credit": arrondi(r["c"]), "solde": arrondi(r["d"] - r["c"])} for r in rows]
    return render(request, "compta/balance.html", {
        "lignes": lignes, "debut": debut, "fin": fin,
        "total_debit": sum((l["debit"] for l in lignes), ZERO), "total_credit": sum((l["credit"] for l in lignes), ZERO),
    })


@login_required
@consulter
def analytique(request):
    debut, fin = periode(request)
    ls = lignes_periode(debut, fin)
    return render(request, "compta/analytique.html", {"debut": debut, "fin": fin, "axe1": resultat_par_axe(ls, 1),
                                                      "axe2": resultat_par_axe(ls, 2)})


@login_required
@consulter
def controles(request):
    res = ctrl.executer()
    etat, a_verifier = ctrl.etat_general(res)
    return render(request, "compta/controles.html", {"resultats": res, "etat": etat, "a_verifier": a_verifier})


@login_required
@consulter
def modifications(request):
    return render(request, "compta/modifications.html", {"page": Paginator(Modification.objects.all(), 100).get_page(request.GET.get("page"))})
