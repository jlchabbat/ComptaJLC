"""Analyse par axes de comptes : chaque compte porte des valeurs sur des axes libres (RubDecl, RubCh, RubType, Cat,
Groupe…), plus trois axes intégrés (Compte, Classe, Axe 1). On choisit un axe en lignes, un axe en colonnes
(facultatif), des filtres sur les autres axes et la période ; les montants sont les soldes débit − crédit des comptes."""

from collections import OrderedDict, defaultdict

from django.db.models import Sum

from .models import ZERO, AxeCompte, Compte, Ligne, ValeurCompte, arrondi

INTEGRES = ["Compte", "Classe", "Axe 1"]
SANS = "(sans)"


def axes():
    return INTEGRES + list(AxeCompte.objects.values_list("nom", flat=True))


def valeurs_par_compte():
    """{compte: {axe: valeur}} pour tous les axes."""
    res = defaultdict(dict)
    for c in Compte.objects.select_related("anal1"):
        res[c.numero].update({"Compte": f"{c.numero} {c.libelle}", "Classe": c.numero[:1],
                              "Axe 1": f"{c.anal1_id} {c.anal1.libelle}".strip() if c.anal1_id else SANS})
    for v in ValeurCompte.objects.select_related("axe"):
        res[v.compte_id][v.axe.nom] = v.valeur
    return res


def choix_filtres():
    """{axe: [valeurs]} pour les listes de filtres."""
    res = OrderedDict((a, set()) for a in axes())
    for vals in valeurs_par_compte().values():
        for a in res:
            res[a].add(vals.get(a, SANS))
    return OrderedDict((a, sorted(v)) for a, v in res.items())


def analyser(debut, fin, lignes_axe, colonnes_axe="", filtres=None, mesure="solde"):
    """Tableau croisé : {'colonnes': [...], 'lignes': [{'valeur', 'cellules', 'total', 'comptes': [...]}], 'totaux', 'total'}."""
    filtres = {a: set(v) for a, v in (filtres or {}).items() if v}
    vals = valeurs_par_compte()
    montants = (Ligne.objects.filter(mouvement__date__range=(debut, fin)).exclude(mouvement__origine="cloture")
                .values("compte_id").annotate(d=Sum("debit"), c=Sum("credit")))
    par_compte = {}
    for m in montants:
        d, c = arrondi(m["d"] or ZERO), arrondi(m["c"] or ZERO)
        par_compte[m["compte_id"]] = {"debit": d, "credit": c, "solde": d - c}[mesure]
    cellules = defaultdict(lambda: defaultdict(lambda: ZERO))
    comptes = defaultdict(list)
    colonnes = set()
    for compte, montant in par_compte.items():
        v = vals.get(compte, {})
        if any(v.get(a, SANS) not in choix for a, choix in filtres.items()) or not montant:
            continue
        ligne = v.get(lignes_axe, SANS)
        col = v.get(colonnes_axe, SANS) if colonnes_axe else "Montant"
        cellules[ligne][col] += montant
        colonnes.add(col)
        comptes[ligne].append((compte, v.get("Compte", compte), col, montant))
    colonnes = sorted(colonnes)
    res = []
    for ligne in sorted(cellules):
        res.append({"valeur": ligne, "cellules": [cellules[ligne].get(c, ZERO) for c in colonnes],
                    "total": sum(cellules[ligne].values(), ZERO), "comptes": sorted(comptes[ligne])})
    totaux = [sum((cellules[l].get(c, ZERO) for l in cellules), ZERO) for c in colonnes]
    return {"colonnes": colonnes, "lignes": res, "totaux": totaux, "total": sum(totaux, ZERO)}
