"""Classeur de saisie à distance, sans grand livre.

    python src/classeur_saisie.py ComptaJLC.xlsm ComptaJLC_Saisie.xlsx

Construit, à partir du classeur maître, un classeur léger pour un saisisseur
bénévole. Il contient :
- l'onglet Saisie du maître : mêmes contrôles et mêmes écritures générées ;
- les modèles d'opérations ;
- les référentiels en valeurs : plan comptable, axes 1 et 2, journaux ;
- les dates d'exercice.

Le grand livre (T_Ecritures) n'y est pas. Les lignes saisies s'accumulent dans
l'onglet Envoi (table T_Envoi, mêmes colonnes que T_Ecritures, Mvt numérotés à
partir de 1). Le trésorier les colle dans l'onglet Transmission du maître, qui
leur donne leur numéro définitif.

Le classeur est à régénérer quand les référentiels du maître changent
(nouveau membre, nouveau code…). La date d'extraction est indiquée dans
l'Accueil.
"""

import datetime as dt
import re
import sys
import tempfile
from pathlib import Path

import openpyxl
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.table import Table, TableStyleInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lot0_preparation import AUJOURDHUI, Feuille, Paquet, ajouter_override, feuilles  # noqa: E402
from lot1_saisie import S_DATE, S_MONTANT, S_NOTE, S_TITRE, Classeur, onglet_modeles, onglet_saisie, remplir  # noqa: E402

COLONNES = ["Date", "Jnl", "Mvt", "Pièce", "Compte", "Intitulé", "Libellé", "Débit", "Crédit", "Solde", "Anal1", "Anal2", "Let"]


def serial(v):
    if isinstance(v, dt.datetime):
        v = v.date()
    return (v - dt.date(1899, 12, 30)).days


def lire_maitre(chemin):
    wb = openpyxl.load_workbook(chemin, data_only=True)
    lignes = lambda ws, n: [r[:n] for r in wb[ws].iter_rows(min_row=2, values_only=True) if r[0] not in (None, "")]
    p = wb["Paramètres"]
    return {
        "plan": [(str(a), b, c) for a, b, c in lignes("Plan comptable", 3)],
        "axe1": lignes("Axe 1 - Anal1", 3),
        "axe2": lignes("Axe 2 - Anal2", 3),
        "journaux": [(a, b) for a, b in lignes("Journaux", 2)],
        "params": {"P_DebutExercice": serial(p["E5"].value), "P_FinExercice": serial(p["E6"].value),
                   "P_DateCloture": serial(p["E7"].value), "P_CompteVirement": str(p["E9"].value)},
    }


def base_openpyxl(donnees, chemin):
    wb = openpyxl.Workbook()
    acc = wb.active
    acc.title = "Accueil"
    envoi = wb.create_sheet("Envoi")
    ref = wb.create_sheet("Référentiels")
    par = wb.create_sheet("Paramètres")

    textes = [
        ("B1", "ComptaJLC – classeur de saisie à distance"),
        ("B3", f"Référentiels extraits du classeur maître le {AUJOURDHUI:%d/%m/%Y}. Ne pas les modifier : demander au trésorier "
               "un nouveau classeur quand un membre ou un événement manque."),
        ("B5", "1. Onglet Saisie : remplir les cases jaunes ; quand tous les contrôles sont OK, les lignes à reporter sont en vert."),
        ("B6", "2. Les copier, puis dans l'onglet Envoi : cliquer la première ligne vide sous la table › Collage spécial › Valeurs "
               "(cocher « Blancs non compris »)."),
        ("B7", "3. Vider les cases jaunes et recommencer pour l'opération suivante."),
        ("B8", "4. Enregistrer le classeur (OneDrive le transmet) et prévenir le trésorier. Il reporte les lignes, puis vide l'onglet Envoi."),
    ]
    for c, t in textes:
        acc[c] = t

    for j, h in enumerate(COLONNES):
        envoi.cell(1, j + 1, h)
    envoi.add_table(Table(displayName="T_Envoi", ref="A1:M2", tableStyleInfo=TableStyleInfo(name="TableStyleLight9", showRowStripes=True)))

    def table(ws, nom, col0, entetes, lignes):
        for j, h in enumerate(entetes):
            ws.cell(1, col0 + j, h)
        for i, ligne in enumerate(lignes):
            for j, v in enumerate(ligne):
                ws.cell(2 + i, col0 + j, v if v is not None else None)
        a = openpyxl.utils.get_column_letter(col0)
        b = openpyxl.utils.get_column_letter(col0 + len(entetes) - 1)
        ws.add_table(Table(displayName=nom, ref=f"{a}1:{b}{1 + max(1, len(lignes))}",
                           tableStyleInfo=TableStyleInfo(name="TableStyleLight9", showRowStripes=True)))

    table(ref, "T_PlanComptable", 1, ["Compte", "Libellé compte", "Axe 1 (Anal1)"], donnees["plan"])
    table(ref, "T_Axe1", 5, ["Code", "Libellé", "Actif"], donnees["axe1"])
    table(ref, "T_Axe2", 9, ["Code", "Libellé", "Actif"], donnees["axe2"])
    table(ref, "T_Journaux", 13, ["Code", "Intitulé"], donnees["journaux"])

    par["A1"] = "Paramètres (copiés du classeur maître)"
    for r, (nom, v) in enumerate(donnees["params"].items(), start=3):
        par.cell(r, 1, nom)
        par.cell(r, 2, v)
        wb.defined_names[nom] = DefinedName(nom, attr_text=f"Paramètres!$B${r}")
    for nom, ref_ in (("L_Comptes", "T_PlanComptable[Compte]"), ("L_Anal1", "T_Axe1[Code]"), ("L_Anal2", "T_Axe2[Code]"),
                      ("L_Journaux", "T_Journaux[Code]")):
        wb.defined_names[nom] = DefinedName(nom, attr_text=ref_)
    wb.save(chemin)


def ajouter_sst(chemin):
    """openpyxl écrit les textes en ligne : on ajoute une table de chaînes partagées vide."""
    p = Paquet(chemin)
    if "xl/sharedStrings.xml" not in p.brut:
        p.ecrire("xl/sharedStrings.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="0" uniqueCount="0"></sst>')
        ajouter_override(p, "xl/sharedStrings.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml")
        rels = p.lire("xl/_rels/workbook.xml.rels")
        rid = "rId" + str(max(int(v) for v in re.findall(r'Id="rId(\d+)"', rels)) + 1)
        p.ecrire("xl/_rels/workbook.xml.rels", rels.replace("</Relationships>",
                 f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" '
                 'Target="sharedStrings.xml"/></Relationships>'))
        p.enregistrer(chemin)
    return chemin


def reprendre_parts(p, maitre):
    """Styles, thème et métadonnées des tableaux dynamiques repris du maître."""
    z = Paquet(maitre)
    for part in ("xl/styles.xml", "xl/theme/theme1.xml"):
        p.ecrire(part, z.brut[part])
    p.ecrire("xl/metadata.xml", z.brut["xl/metadata.xml"])
    ajouter_override(p, "xl/metadata.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheetMetadata+xml")
    rels = p.lire("xl/_rels/workbook.xml.rels")
    rid = "rId" + str(max(int(v) for v in re.findall(r'Id="rId(\d+)"', rels)) + 1)
    p.ecrire("xl/_rels/workbook.xml.rels", rels.replace("</Relationships>",
             f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sheetMetadata" '
             'Target="metadata.xml"/></Relationships>'))


def main(maitre, sortie, entrees=None):
    donnees = lire_maitre(maitre)
    with tempfile.TemporaryDirectory() as d:
        base = Path(d) / "base.xlsx"
        base_openpyxl(donnees, base)
        cl = Classeur(ajouter_sst(base))
    reprendre_parts(cl.p, maitre)
    onglet_modeles(cl)
    cl.noms.pop("L_Prefixes", None)      # pas de préfixes dans le classeur de saisie
    part = onglet_saisie(cl)
    # la saisie alimente T_Envoi (onglet Envoi) au lieu de T_Ecritures
    s = cl.p.lire(part).replace("T_Ecritures[", "T_Envoi[").replace("Écritures", "Envoi")
    cl.p.ecrire(part, s)
    cl.ch.si = [e.replace("table Écritures", "table Envoi").replace("dans Écritures", "dans Envoi") for e in cl.ch.si]
    cl.enregistrer_noms()
    # mise en forme minimale des onglets créés par openpyxl
    f = feuilles(cl.p)
    fe = Feuille(cl.p, f["Envoi"])
    for c, st in (("A", S_DATE), ("H", S_MONTANT), ("I", S_MONTANT), ("J", S_MONTANT)):
        fe.poser(f"{c}2", f'<c r="{c}2" s="{st}"/>')
    fe.enregistrer()
    fe = Feuille(cl.p, f["Accueil"])
    for ref, s in (("B1", S_TITRE), ("B3", S_NOTE), ("B5", None), ("B6", None), ("B7", None), ("B8", None)):
        cel = fe.cellule(ref)
        if s is not None:
            fe.poser(ref, re.sub(r'<c r="(\w+)"', rf'<c r="\1" s="{s}"', cel, count=1))
    fe.enregistrer()
    fe = Feuille(cl.p, f["Paramètres"])
    for r in (3, 4, 5):
        cel = fe.cellule(f"B{r}")
        fe.poser(f"B{r}", re.sub(r'<c r="(\w+)"', rf'<c r="\1" s="{S_DATE}"', cel, count=1))
    fe.enregistrer()
    if entrees:
        remplir(cl, entrees)
    cl.ch.enregistrer()
    cl.p.enregistrer(sortie)
    print(f"{sortie} : classeur de saisie ({len(donnees['plan'])} comptes, {len(donnees['axe2'])} codes Anal2)")



if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
