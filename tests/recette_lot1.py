"""Recette du Lot 1 par recalcul LibreOffice (headless).

    python tests/recette_lot1.py ComptaBB_lot0.xlsm [dossier_de_travail]

Pour chaque scénario : applique le Lot 1 au classeur du Lot 0 en remplissant
les cases jaunes, fait recalculer le classeur par LibreOffice (conversion
xlsx), puis compare les écritures générées et les contrôles au résultat
attendu. Nécessite LibreOffice (soffice) avec son module Calc.

LibreOffice ne connaît pas encore LET, FILTER ni SORT : la liste des tiers
et le « Code suivant » des préfixes ne se vérifient que dans Excel.
"""

import datetime as dt
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import lot1_saisie  # noqa: E402


def d(a, m, j):
    return (dt.date(a, m, j) - dt.date(1899, 12, 30)).days


TAIEB = "TAIEB JEANNE (411TAIEB001)"
BASE = {"Saisie!C4": d(2026, 10, 15), "Saisie!C7": 400}

# nom : (entrées, lignes attendues [(Jnl, Mvt, Compte, Débit, Crédit)] ou None, erreurs attendues {contrôle})
SCENARIOS = {
    "cotisation_reglee": ({**BASE, "Saisie!C5": "Cotisation membre", "Saisie!C6": TAIEB, "Saisie!C8": "BIT", "Saisie!C10": "GEN.002"},
                          [("B3", 422, "411TAIEB001", 400, 0), ("B3", 422, "700000", 0, 400),
                           ("B3", 422, "512200", 400, 0), ("B3", 422, "411TAIEB001", 0, 400)], set()),
    "cotisation_non_reglee": ({**BASE, "Saisie!C5": "Cotisation membre", "Saisie!C6": TAIEB, "Saisie!C8": "Non réglé",
                               "Saisie!C10": "GEN.002"},
                              [("VT", 422, "411TAIEB001", 400, 0), ("VT", 422, "700000", 0, 400)], set()),
    "frais_bancaires": ({**BASE, "Saisie!C5": "Frais bancaires", "Saisie!C7": 25, "Saisie!C8": "Mizrahi compte courant",
                         "Saisie!C10": "GEN.004"},
                        [("B1", 422, "600100", 25, 0), ("B1", 422, "512000", 0, 25)], set()),
    "virement_interne": ({**BASE, "Saisie!C5": "Virement interne", "Saisie!C7": 1000, "Saisie!C8": "Mizrahi compte courant",
                          "Saisie!C9": "BIT", "Saisie!C10": "GEN.001"},
                         [("B1", 422, "580000", 1000, 0), ("B1", 422, "512000", 0, 1000),
                          ("B3", 423, "512200", 1000, 0), ("B3", 423, "580000", 0, 1000)], set()),
    "isracard": ({**BASE, "Saisie!C5": "Paiement carte Isracard", "Saisie!C7": 500, "Saisie!C8": "Mizrahi compte courant",
                  "Saisie!C10": "GEN.004"},
                 [("OD", 422, "600000", 500, 0), ("OD", 422, "580000", 0, 500),
                  ("B1", 423, "580000", 500, 0), ("B1", 423, "512000", 0, 500)], set()),
    "remboursement": ({**BASE, "Saisie!C5": "Cotisation membre", "Saisie!C6": TAIEB, "Saisie!C8": "BIT", "Saisie!C10": "GEN.002",
                       "Saisie!C12": "Oui"},
                      [("B3", 422, "411TAIEB001", 0, 400), ("B3", 422, "700000", 400, 0),
                       ("B3", 422, "512200", 0, 400), ("B3", 422, "411TAIEB001", 400, 0)], set()),
    "facture_fournisseur_caisse": ({**BASE, "Saisie!C5": "Facture fournisseur", "Saisie!C6": "FOURNIS DIVERS (401000)",
                                    "Saisie!C8": "Caisse (espèces)", "Saisie!C10": "MAN.001", "Saisie!C11": "610000"},
                                   [("CA", 422, "610000", 400, 0), ("CA", 422, "401000", 0, 400),
                                    ("CA", 422, "401000", 400, 0), ("CA", 422, "530000", 0, 400)], set()),
    "fournisseur_sans_compte": ({**BASE, "Saisie!C5": "Facture fournisseur", "Saisie!C6": "FOURNIS DIVERS (401000)",
                                 "Saisie!C8": "Caisse (espèces)", "Saisie!C10": "MAN.001"}, None, {"Compte"}),
    "date_close_et_mauvais_tiers": ({**BASE, "Saisie!C4": d(2025, 12, 15), "Saisie!C5": "Cotisation membre",
                                     "Saisie!C6": "FOURNIS DIVERS (401000)", "Saisie!C8": "BIT", "Saisie!C10": "GEN.002"},
                                    None, {"Date", "Tiers"}),
    "depense_classe_7": ({**BASE, "Saisie!C5": "Dépense directe", "Saisie!C8": "BIT", "Saisie!C10": "GEN.001",
                          "Saisie!C11": "700000"}, None, {"Compte"}),
    "paiement_manquant": ({**BASE, "Saisie!C5": "Frais bancaires", "Saisie!C10": "GEN.004"}, None, {"Moyen de paiement"}),
    "virement_meme_compte": ({**BASE, "Saisie!C5": "Virement interne", "Saisie!C8": "BIT", "Saisie!C9": "BIT",
                              "Saisie!C10": "GEN.001"}, None, {"Virement : compte qui reçoit"}),
    "deja_reportee": ({"Saisie!C4": d(2026, 9, 24), "Saisie!C5": "Facture manifestation (membre)", "Saisie!C6": TAIEB,
                       "Saisie!C7": 400, "Saisie!C8": "Mizrahi compte courant", "Saisie!C10": "MAN.001",
                       "Saisie!C13": "FACTURE 40013 - TAIEB JEANNE"}, None, {"Déjà reportée ?"}),
    "codes": ({"Codes!C3": "Trésorier", "Codes!C17": "Taïeb", "Codes!C18": "Paul", "Codes!C29": "SOC.006", "Codes!C33": "2"},
              None, set()),
    "codes_confirme": ({"Codes!C29": "SOC.006", "Codes!C33": "2", "Codes!C34": "Oui"}, None, set()),
}


def recalculer(fichiers, dossier):
    profil = Path(dossier) / "profil"
    (profil / "user").mkdir(parents=True, exist_ok=True)
    (profil / "user" / "registrymodifications.xcu").write_text(
        '<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry" '
        'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse">'
        '<value>0</value></prop></item></oor:items>', encoding="utf-8")
    sortie = Path(dossier) / "recalcul"
    sortie.mkdir(exist_ok=True)
    subprocess.run(["soffice", f"-env:UserInstallation=file://{profil}", "--headless", "--convert-to", "xlsx",
                    "--outdir", str(sortie)] + [str(f) for f in fichiers], check=True, capture_output=True, timeout=900)
    return sortie


def lire(wb):
    ws = wb["Saisie"]
    lignes = []
    for r in range(lot1_saisie.L_APERCU, lot1_saisie.L_APERCU + lot1_saisie.NB_LIGNES):
        v = [ws.cell(r, c).value for c in range(2, 11)]
        if v[1] not in (None, ""):
            lignes.append((v[1], int(v[2]), str(v[4]), float(v[7] or 0), float(v[8] or 0)))
    controles = {ws.cell(r, 2).value: (ws.cell(r, 3).value, ws.cell(r, 4).value) for r in range(18, 29)}
    zone = [[ws.cell(r, c).value for c in range(2, 15)] for r in range(lot1_saisie.L_ZONE, lot1_saisie.L_ZONE + lot1_saisie.NB_LIGNES)]
    return lignes, controles, ws["B16"].value, zone


def main(lot0, dossier=None):
    dossier = Path(dossier or tempfile.mkdtemp())
    fichiers = []
    for nom, (entrees, _, _) in SCENARIOS.items():
        f = dossier / f"{nom}.xlsm"
        lot1_saisie.main(lot0, f, entrees)
        fichiers.append(f)
    sortie = recalculer(fichiers, dossier)
    echecs = 0
    for nom, (entrees, attendu, erreurs) in SCENARIOS.items():
        wb = openpyxl.load_workbook(sortie / f"{nom}.xlsx", data_only=True)
        if nom.startswith("codes"):
            c = wb["Codes"]
            vus = {k: c[k].value for k in ("C19", "C20", "C24", "D24", "E25", "C37", "D37", "G39", "H39", "I39")}
            ok = (vus["C19"] == "411TAIEB002" and vus["C24"] == "OK") if nom == "codes" else vus["C37"] == "OK"
            if nom == "codes":
                ok = ok and vus["C37"] == "Erreur"
            print(("OK   " if ok else "ÉCHEC"), nom, vus)
            echecs += not ok
            continue
        lignes, controles, statut, zone = lire(wb)
        en_erreur = {k for k, (res, _) in controles.items() if res == "Erreur"}
        ok = en_erreur == erreurs and (attendu is None or [(j, m, c, round(dd, 2), round(cc, 2)) for j, m, c, dd, cc in lignes] == attendu)
        if attendu is not None:
            zone_ok = [z for z in zone if z[0] not in (None, "")]
            ok = ok and len(zone_ok) == len(attendu) and all(z[5] is None and z[10] is None for z in zone_ok)
        print(("OK   " if ok else "ÉCHEC"), nom, "|", statut)
        if not ok:
            echecs += 1
            print("     lignes :", lignes)
            print("     erreurs :", {k: v for k, v in controles.items() if v[0] == "Erreur"})
    print(f"{len(SCENARIOS) - echecs}/{len(SCENARIOS)} scénarios conformes")
    return 1 if echecs else 0


if __name__ == "__main__":
    if not shutil.which("soffice"):
        sys.exit("LibreOffice (soffice) introuvable")
    sys.exit(main(*sys.argv[1:]))
