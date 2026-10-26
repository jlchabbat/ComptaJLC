"""Tableau croisé dynamique (TCD) des écritures, comme dans Excel.

Champs : Anal et les axes fixes du plan (RubDecl, RubCh…), valeurs portées par les comptes, plus Compte, Journal et
Mois. On choisit jusqu'à trois champs en lignes (imbriqués, avec sous-totaux), un champ en colonnes, des filtres sur
chaque champ, la valeur (résultat, solde, débits ou crédits) et le type de comptes (gestion 6-7, bilan 1-5, tous)."""

from collections import OrderedDict

from django.db.models import Q, Sum
from django.db.models.functions import TruncMonth

from .axes_comptes import SANS, valeurs_par_compte
from .models import ZERO, AxeCompte, Ligne, arrondi

AUTRES = ["Compte", "Journal", "Mois"]
VALEURS = OrderedDict([
    ("resultat", ("Résultat (crédit − débit)", lambda d, c: c - d)),
    ("solde", ("Solde (débit − crédit)", lambda d, c: d - c)),
    ("debit", ("Débits", lambda d, c: d)),
    ("credit", ("Crédits", lambda d, c: c)),
])
TYPES = OrderedDict([("gestion", ("Gestion (comptes 6 et 7)", "67")), ("bilan", ("Bilan (comptes 1 à 5)", "12345")),
                     ("tous", ("Tous les comptes", "123456789"))])


def champs():
    """Champs proposés : Anal, axes du plan, puis Compte, Journal, Mois."""
    return ["Anal"] + list(AxeCompte.objects.values_list("nom", flat=True)) + AUTRES


def enregistrements(debut, fin, type_comptes="gestion"):
    """[{champ: valeur, 'd': débits, 'c': crédits}] : un par compte, journal et mois de la période."""
    q = Q()
    for c in TYPES[type_comptes][1]:
        q |= Q(compte__numero__startswith=c)
    rows = (Ligne.objects.filter(q, mouvement__date__range=(debut, fin))
            .values("compte_id", "mouvement__journal_id", mois=TruncMonth("mouvement__date"))
            .annotate(d=Sum("debit"), c=Sum("credit")))
    attributs = valeurs_par_compte()
    res = []
    for r in rows:
        a = attributs.get(r["compte_id"], {})
        e = {ch: a.get(ch) or SANS for ch in champs()[:-len(AUTRES)]}
        e.update({"Compte": a.get("Compte", r["compte_id"]), "Journal": r["mouvement__journal_id"],
                  "Mois": f"{r['mois']:%Y-%m}", "d": r["d"] or ZERO, "c": r["c"] or ZERO, "compte": r["compte_id"]})
        res.append(e)
    return res


def valeurs_des_champs(enrs):
    """{champ: [valeurs triées]} pour les filtres."""
    return OrderedDict((ch, sorted({e[ch] for e in enrs})) for ch in champs())


def filtrer(enrs, filtres):
    """Garde les enregistrements dont la valeur est cochée sur chaque champ filtré ({champ: [valeurs]})."""
    actifs = {ch: set(v) for ch, v in (filtres or {}).items() if v}
    return [e for e in enrs if all(e[ch] in v for ch, v in actifs.items())]


def tableau(enrs, lignes, colonne="", valeur="resultat"):
    """Lignes imbriquées avec sous-totaux : {'colonnes', 'lignes': [{niveau, chemin, libelle, cellules, total, feuille}],
    'totaux', 'total'} ; les lignes d'un groupe suivent sa ligne de sous-total, dans l'ordre des valeurs."""
    calcul = VALEURS[valeur][1]
    colonnes = sorted({e[colonne] for e in enrs}) if colonne else []
    index = {c: i for i, c in enumerate(colonnes)}

    def vide():
        return {"cellules": [ZERO] * len(colonnes), "total": ZERO, "enfants": OrderedDict()}

    racine = vide()
    for e in sorted(enrs, key=lambda e: [e[ch] for ch in lignes]):
        m = calcul(e["d"], e["c"])
        noeuds = [racine]
        for ch in lignes:
            noeuds.append(noeuds[-1]["enfants"].setdefault(e[ch], vide()))
        for n in noeuds:
            n["total"] += m
            if colonne:
                n["cellules"][index[e[colonne]]] += m
    res = []

    def parcourir(noeud, niveau, chemin):
        for valeur_, enfant in noeud["enfants"].items():
            if not enfant["total"] and not any(enfant["cellules"]):
                continue                                   # combinaison sans montant : pas de ligne
            c = chemin + [valeur_]
            res.append({"niveau": niveau, "chemin": c, "libelle": valeur_, "feuille": niveau == len(lignes) - 1,
                        "cellules": [arrondi(x) for x in enfant["cellules"]], "total": arrondi(enfant["total"])})
            parcourir(enfant, niveau + 1, c)

    parcourir(racine, 0, [])
    garder = [i for i in range(len(colonnes)) if any(l["cellules"][i] for l in res if l["niveau"] == 0)]  # colonnes vides masquées
    for l in res:
        l["cellules"] = [l["cellules"][i] for i in garder]
    return {"colonnes": [colonnes[i] for i in garder], "lignes": res,
            "totaux": [arrondi(racine["cellules"][i]) for i in garder], "total": arrondi(racine["total"])}


def comptes_de(enrs, criteres):
    """Comptes, journaux et mois des enregistrements qui ont ces valeurs ({champ: valeur}) : pour lister les écritures."""
    choisis = [e for e in enrs if all(e[ch] == v for ch, v in criteres.items())]
    return choisis
