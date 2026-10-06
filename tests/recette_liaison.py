"""Recette du fichier de liaison par recalcul LibreOffice.

    python tests/recette_liaison.py ComptaJLC.xlsm [dossier_de_travail]

1. Fichier de liaison rempli (activité MAN.001 + gestion) : l'export doit
   contenir les écritures attendues, et les totaux de l'activité doivent être
   justes.
2. Mêmes données sans les colonnes du trésorier en Gestion : export bloqué.
3. Export collé dans l'onglet Transmission du maître : prêt à reporter, Mvt
   définitifs 422 à 428.
"""

import datetime as dt
import shutil
import sys
import tempfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import classeur_liaison  # noqa: E402
import lot1_distance  # noqa: E402
from recette_lot1 import recalculer  # noqa: E402

TAIEB = "TAIEB JEANNE (411TAIEB001)"


def d(a, m, j):
    return (dt.date(a, m, j) - dt.date(1899, 12, 30)).days


def colonnes(wb, onglet, ligne):
    ws = wb[onglet]
    return {c.value: c.column_letter for c in ws[ligne] if c.value}


def entrees(chemin, avec_tresorier=True, provisoire=False):
    wb = openpyxl.load_workbook(chemin)
    act_r = colonnes(wb, "Activité", 12)
    ges = colonnes(wb, "Gestion", 6)
    # dans chaque onglet, la 2e table (dépenses) répète les en-têtes : on les distingue par position
    def cols(onglet, ligne):
        ws = wb[onglet]
        entetes = [(c.column, c.value) for c in ws[ligne] if c.value]
        coupe = [i for i, (_, h) in enumerate(entetes) if h == "Date"][1]
        a = {h: openpyxl.utils.get_column_letter(c) for c, h in entetes[:coupe]}
        b = {h: openpyxl.utils.get_column_letter(c) for c, h in entetes[coupe:]}
        return a, b
    ra, da = cols("Activité", 12)
    rg, dg = cols("Gestion", 6)
    _ = (act_r, ges)
    e = {"Activité!C3": "MAN.001", "Activité!C4": "Responsable test"}
    recettes = [
        {"Date": d(2026, 10, 15), "Membre": TAIEB, "Nb pers.": 2, "Montant": 200, "Mode": "Bit"},
        {"Date": d(2026, 10, 15), "Autre payeur": "DUPONT MARC", "Nb pers.": 1, "Montant": 100, "Mode": "Espèces"},
        {"Date": d(2026, 10, 15), "Membre": TAIEB, "Montant": 150, "Mode": "Non payé"},
    ]
    depenses = [
        {"Date": d(2026, 10, 16), "Bénéficiaire": "TRAITEUR COHEN", "Nature": "Manifestation (traiteur, artiste, matériel…)",
         "Montant": 250, "Payé par": "Chèque"},
        {"Date": d(2026, 10, 16), "Bénéficiaire": "IMPRIMERIE", "Nature": "Frais divers", "Montant": 40,
         "Payé par": "Avance d'un membre", "Membre (si avance)": TAIEB},
    ]
    for i, ligne in enumerate(recettes):
        for h, v in ligne.items():
            e[f"Activité!{ra[h]}{13 + i}"] = v
    for i, ligne in enumerate(depenses):
        for h, v in ligne.items():
            e[f"Activité!{da[h]}{13 + i}"] = v
    rec_g = {"Date": d(2026, 10, 17), "Origine (qui donne)": "FAMILLE LEVY", "Nature": "Don reçu", "Montant": 500}
    dep_g = {"Date": d(2026, 10, 17), "Bénéficiaire": "FAMILLE X", "Nature": "Aide versée", "Montant": 300}
    if avec_tresorier:
        rec_g.update({"Mode (trésorier)": "Virement Mizrahi", "Compte (trésorier)": "725000", "Code Axe2 (trésorier)": "GEN.003"})
        dep_g.update({"Mode (trésorier)": "Espèces", "Compte (trésorier)": "630000", "Code Axe2 (trésorier)": "SOC.007"})
    if provisoire:
        ws = openpyxl.load_workbook(chemin)["Tiers"]
        n = next(r for r in range(5, ws.max_row + 2) if ws.cell(r, 1).value is None)
        e[f"Tiers!A{n}"] = "NOUVEAU MEMBRE TEST"
        e[f"Tiers!C{n}"] = "Membre"
        e[f"Activité!{ra['Membre']}16"] = "NOUVEAU MEMBRE TEST"
        e[f"Activité!{ra['Date']}16"] = d(2026, 10, 15)
        e[f"Activité!{ra['Montant']}16"] = 80
        e[f"Activité!{ra['Mode']}16"] = "Espèces"
    for h, v in rec_g.items():
        e[f"Gestion!{rg[h]}7"] = v
    for h, v in dep_g.items():
        e[f"Gestion!{dg[h]}7"] = v
    return e


ATTENDU = [
    ("B3", 1001, "411TAIEB001", 200, 0), ("B3", 1001, "710000", 0, 200), ("B3", 1001, "512200", 200, 0),
    ("B3", 1001, "411TAIEB001", 0, 200), ("CA", 1002, "530000", 100, 0), ("CA", 1002, "710000", 0, 100),
    ("VT", 1003, "411TAIEB001", 150, 0), ("VT", 1003, "710000", 0, 150),
    ("B1", 2001, "610000", 250, 0), ("B1", 2001, "512000", 0, 250),
    ("OD", 2002, "600000", 40, 0), ("OD", 2002, "411TAIEB001", 0, 40),
    ("B1", 3001, "512000", 500, 0), ("B1", 3001, "725000", 0, 500),
    ("CA", 4001, "630000", 300, 0), ("CA", 4001, "530000", 0, 300),
]


def main(maitre, dossier=None):
    dossier = Path(dossier or tempfile.mkdtemp())
    vide = dossier / "vide.xlsx"
    classeur_liaison.construire(maitre, vide)
    complet, incomplet = dossier / "liaison.xlsx", dossier / "liaison_incomplete.xlsx"
    classeur_liaison.construire(maitre, complet, entrees(vide, True))
    classeur_liaison.construire(maitre, incomplet, entrees(vide, False))
    provisoire = dossier / "liaison_provisoire.xlsx"
    classeur_liaison.construire(maitre, provisoire, entrees(vide, True, provisoire=True))
    sortie = recalculer([complet, incomplet, provisoire], dossier)
    echecs = 0

    wb = openpyxl.load_workbook(sortie / "liaison.xlsx", data_only=True)
    x = wb["Export"]
    lignes = []
    brut = []
    for r in range(6, 6 + classeur_liaison.NB_EXPORT):
        v = [x.cell(r, c).value for c in range(1, 14)]
        if v[0] in (None, ""):
            break
        brut.append(v)
        lignes.append((v[1], int(v[2]), str(v[4]), round(float(v[7]), 2), round(float(v[8]), 2)))
    a = wb["Activité"]
    totaux = (a["C7"].value, a["C8"].value, a["C9"].value, a["C10"].value)
    ok = lignes == ATTENDU and totaux == (3, 450, 290, 160)
    print(("OK   " if ok else "ÉCHEC"), "liaison complète :", x["A3"].value, "| totaux activité", totaux)
    if not ok:
        print("     ", lignes)
    echecs += not ok

    wb = openpyxl.load_workbook(sortie / "liaison_incomplete.xlsx", data_only=True)
    x = wb["Export"]
    ok = str(x["A3"].value).startswith("À COMPLÉTER") and x["A6"].value in (None, "")
    ctrl = [c.value for c in wb["Gestion"][7] if isinstance(c.value, str) and "trésorier" in c.value]
    print(("OK   " if ok else "ÉCHEC"), "liaison sans colonnes trésorier :", x["A3"].value, "|", ctrl[:1])
    echecs += not ok

    wb = openpyxl.load_workbook(sortie / "liaison_provisoire.xlsx", data_only=True)
    x = wb["Export"]
    ctrl = [c.value for c in wb["Activité"][16] if isinstance(c.value, str) and "provisoire" in c.value]
    ok = str(x["A3"].value).startswith("À COMPLÉTER") and bool(ctrl)
    print(("OK   " if ok else "ÉCHEC"), "tiers provisoire :", x["A3"].value, "|", ctrl[:1])
    echecs += not ok

    # export collé dans Transmission
    recu = [[v if v not in ("",) else None for v in ligne] for ligne in brut]
    for ligne in recu:
        ligne[0] = d(ligne[0].year, ligne[0].month, ligne[0].day) if isinstance(ligne[0], dt.datetime) else ligne[0]
    master = dossier / "transmission.xlsm"
    lot1_distance.main(maitre_lot1(maitre, dossier), master, recu=recu)
    sortie2 = recalculer([master], dossier / "t")
    t = openpyxl.load_workbook(sortie2 / "transmission.xlsx", data_only=True)["Transmission"]
    mvts = sorted({t.cell(r, 14).value for r in range(7, 7 + len(recu))})
    ok = str(t["A3"].value).startswith("PRÊT") and mvts == list(range(422, 429))
    print(("OK   " if ok else "ÉCHEC"), "Transmission :", t["A3"].value, "| Mvt", mvts)
    echecs += not ok
    print(f"{4 - echecs}/4 cas conformes")
    return 1 if echecs else 0


def maitre_lot1(maitre, dossier):
    """Transmission s'ajoute au classeur du Lot 1 (1re partie) : on le retrouve à côté du maître s'il existe."""
    lot1 = Path(maitre).with_name("lot1.xlsm")
    if not lot1.exists():
        sys.exit("lot1.xlsm introuvable à côté du classeur maître")
    return lot1


if __name__ == "__main__":
    if not shutil.which("soffice"):
        sys.exit("LibreOffice (soffice) introuvable")
    sys.exit(main(*sys.argv[1:]))
