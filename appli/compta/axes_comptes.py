"""Axes de comptes : chaque compte porte des valeurs sur des axes libres (RubDecl, RubCh…), plus trois axes intégrés
(Compte, Classe, Anal). Le tableau croisé (tcd.py) et l'analytique s'en servent."""

from collections import defaultdict

from .models import AxeCompte, Compte, ValeurCompte

INTEGRES = ["Compte", "Classe", "Anal"]
SANS = "(sans)"


def axes():
    return INTEGRES + list(AxeCompte.objects.values_list("nom", flat=True))


def libelle_propre(code):
    """Libellé d'un code Anal, vide s'il ne fait que répéter le code (code créé sans libellé)."""
    return "" if code.libelle in ("", code.code) else code.libelle


def valeurs_par_compte():
    """{compte: {axe: valeur}} pour tous les axes."""
    res = defaultdict(dict)
    for c in Compte.objects.select_related("anal1"):
        res[c.numero].update({"Compte": f"{c.numero} {c.libelle}", "Classe": c.numero[:1],
                              "Anal": f"{c.anal1_id} {libelle_propre(c.anal1)}".strip() if c.anal1_id else SANS})
    for v in ValeurCompte.objects.select_related("axe"):
        res[v.compte_id][v.axe.nom] = v.valeur
    return res
