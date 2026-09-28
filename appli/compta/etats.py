"""États annuels : compte de résultat, bilan simplifié, budget, comparaison N / N-1 (cahier des charges, Lot 4).

Soldes cumulés : après une clôture qui a généré ses à-nouveaux, les comptes de bilan repartent de
l'à-nouveau (1er jour de l'exercice suivant) ; avant, ils cumulent depuis la première écriture."""

import datetime as dt
from collections import OrderedDict

from django.db.models import Case, F, Q, Sum, Value, When

from .models import ZERO, Budget, CodeAnalytique, Compte, Exercice, Ligne, arrondi

CLASSES_BILAN = ("1", "2", "3", "4", "5")
LIBELLES_CLASSES = {"1": "Capitaux", "2": "Immobilisations", "3": "Stocks", "4": "Tiers", "5": "Trésorerie",
                    "6": "Charges", "7": "Produits"}


def origine(jusquau):
    """Premier jour à prendre en compte pour un solde cumulé à cette date (None : depuis le début)."""
    ex = Exercice.objects.filter(mouvement_an__isnull=False, fin__lt=jusquau).order_by("-fin").first()
    return ex.fin + dt.timedelta(days=1) if ex else None


def lignes_cumulees(jusquau):
    qs = Ligne.objects.filter(mouvement__date__lte=jusquau)
    o = origine(jusquau)
    return qs.filter(mouvement__date__gte=o) if o else qs


def solde_cumule(compte, jusquau):
    s = lignes_cumulees(jusquau).filter(compte=compte).aggregate(d=Sum("debit"), c=Sum("credit"))
    return arrondi((s["d"] or ZERO) - (s["c"] or ZERO))


def soldes_par_compte(lignes):
    rows = lignes.values("compte__numero", "compte__libelle").annotate(d=Sum("debit"), c=Sum("credit")).order_by("compte__numero")
    return OrderedDict((r["compte__numero"], (r["compte__libelle"], arrondi(r["d"] - r["c"]))) for r in rows)


def precedent(exercice):
    return Exercice.objects.filter(debut__lt=exercice.debut).order_by("-debut").first() if exercice else None


# ---------------------------------------------------------------- compte de résultat

def compte_de_resultat(ex, ex_prec=None):
    """Charges et produits par compte, N et N-1, avec sous-totaux par classe."""
    def periode(e):
        if not e:
            return {}
        qs = Ligne.objects.filter(mouvement__date__range=(e.debut, e.fin)).filter(
            Q(compte__numero__startswith="6") | Q(compte__numero__startswith="7"))
        return soldes_par_compte(qs)
    n, n1 = periode(ex), periode(ex_prec)
    sections = []
    for classe, signe in (("6", 1), ("7", -1)):
        numeros = sorted({k for k in list(n) + list(n1) if k.startswith(classe)})
        lignes = [{"numero": k, "libelle": (n.get(k) or n1.get(k))[0],
                   "n": signe * n[k][1] if k in n else ZERO, "n1": signe * n1[k][1] if k in n1 else ZERO} for k in numeros]
        sections.append({"titre": LIBELLES_CLASSES[classe], "lignes": lignes,
                         "total_n": sum((l["n"] for l in lignes), ZERO), "total_n1": sum((l["n1"] for l in lignes), ZERO)})
    charges, produits = sections
    return {"sections": sections, "resultat_n": produits["total_n"] - charges["total_n"],
            "resultat_n1": produits["total_n1"] - charges["total_n1"]}


def par_axe(ex, ex_prec, axe):
    """Produits, charges et résultat par code d'axe, N et N-1."""
    champ = "compte__anal1" if axe == 1 else "anal2"
    c7, c6 = Q(compte__numero__startswith="7"), Q(compte__numero__startswith="6")

    def calc(e):
        if not e:
            return {}
        rows = (Ligne.objects.filter(mouvement__date__range=(e.debut, e.fin)).filter(c6 | c7).values(champ).order_by(champ)
                .annotate(p=Sum(Case(When(c7, then=F("credit") - F("debit")), default=Value(ZERO))),
                          ch=Sum(Case(When(c6, then=F("debit") - F("credit")), default=Value(ZERO)))))
        return {r[champ]: (arrondi(r["p"]), arrondi(r["ch"])) for r in rows}
    n, n1 = calc(ex), calc(ex_prec)
    libelles = dict(CodeAnalytique.objects.filter(axe=axe).values_list("code", "libelle"))
    res = []
    for code in sorted(set(n) | set(n1), key=lambda c: c or ""):
        p, ch = n.get(code, (ZERO, ZERO))
        res.append({"code": code, "libelle": libelles.get(code, ""), "produits": p, "charges": ch, "resultat": p - ch,
                    "resultat_n1": (lambda x: x[0] - x[1])(n1.get(code, (ZERO, ZERO)))})
    return res


# ---------------------------------------------------------------- bilan simplifié

def bilan(jusquau, debut_exercice):
    """Comptes de bilan (classes 1 à 5) au solde débiteur à l'actif, créditeur au passif, plus le résultat.

    Le résultat de l'exercice est celui des classes 6 et 7 depuis le début de l'exercice ; les résultats
    d'exercices antérieurs pas encore reportés par des à-nouveaux apparaissent sur une ligne à part."""
    cumul = lignes_cumulees(jusquau)
    comptes = soldes_par_compte(cumul.filter(compte__numero__regex=r"^[1-5]"))
    actif, passif = OrderedDict(), OrderedDict()
    for numero, (libelle, solde) in comptes.items():
        if solde == 0:
            continue
        cote = actif if solde > 0 else passif
        cote.setdefault(numero[0], []).append({"numero": numero, "libelle": libelle, "montant": abs(solde)})
    gestion = cumul.filter(Q(compte__numero__startswith="6") | Q(compte__numero__startswith="7"))
    r_ex = -sum((s for _, s in soldes_par_compte(gestion.filter(mouvement__date__gte=debut_exercice)).values()), ZERO)
    r_ant = -sum((s for _, s in soldes_par_compte(gestion.filter(mouvement__date__lt=debut_exercice)).values()), ZERO)
    total = lambda cote: sum((l["montant"] for ls in cote.values() for l in ls), ZERO)  # noqa: E731
    total_actif, total_passif = total(actif), total(passif) + r_ex + r_ant
    return {"date": jusquau, "actif": [(k, LIBELLES_CLASSES[k], v) for k, v in actif.items()],
            "passif": [(k, LIBELLES_CLASSES[k], v) for k, v in passif.items()], "resultat": r_ex, "resultats_anterieurs": r_ant,
            "total_actif": total_actif, "total_passif": total_passif, "equilibre": total_actif == total_passif}


def comparer(b, b_prec):
    """Ajoute à chaque ligne du bilan le montant N-1 du même compte (même côté)."""
    if not b_prec:
        return b
    for cote in ("actif", "passif"):
        n1 = {l["numero"]: l["montant"] for _, _, ls in b_prec[cote] for l in ls}
        for _, _, ls in b[cote]:
            for l in ls:
                l["n1"] = n1.get(l["numero"])
    return b


def montant(v):
    """Montant au format français avec la devise du site, pour les messages."""
    from .reglages import montant
    return montant(v)


# ---------------------------------------------------------------- budget

def budget(ex):
    """Budget et réalisé de l'exercice, écart en montant et en %."""
    if not ex:
        return []
    ls = Ligne.objects.filter(mouvement__date__range=(ex.debut, ex.fin))
    res = []
    for b in Budget.objects.filter(exercice=ex).select_related("compte", "anal1", "anal2"):
        classe = "6" if b.nature == "C" else "7"
        qs = ls.filter(compte__numero__startswith=classe)
        if b.compte_id:
            qs = qs.filter(compte=b.compte)
        elif b.anal1_id:
            qs = qs.filter(compte__anal1=b.anal1)
        else:
            qs = qs.filter(anal2=b.anal2)
        s = qs.aggregate(d=Sum("debit"), c=Sum("credit"))
        realise = arrondi(((s["d"] or ZERO) - (s["c"] or ZERO)) * (1 if b.nature == "C" else -1))
        ecart = realise - b.montant
        res.append({"budget": b, "realise": realise, "ecart": ecart,
                    "pourcent": round(ecart * 100 / b.montant, 1) if b.montant else None})
    return res


def comptes_sans_budget():
    return Compte.objects.filter(Q(numero__startswith="6") | Q(numero__startswith="7"), actif=True)
