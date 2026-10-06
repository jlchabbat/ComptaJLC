"""Télécharge, sur votre PC, tous les documents dont un classeur Excel donne le lien, dans un ZIP prêt à déposer dans ComptaJLC.

Usage (rien à installer que Python) :   python telecharger_liens.py "Liens_en_ligne.csv"   (liste exportée par ComptaJLC : chaque document
porte le n° de son mouvement) ou python telecharger_liens.py "EXTRACT.xlsx" (classeur Excel de liens).
Résultat : un fichier « Documents_<date>.zip » à côté du classeur. Chaque document est nommé « <date> <montant> <libellé>.pdf » :
ComptaJLC le propose alors au mouvement de même date et même montant (Saisie › Justificatifs › Déposer).
Les liens qui demandent une connexion : être connecté sur le site dans le navigateur ne suffit pas pour ce script ;
ceux-là sont listés en fin de course pour être téléchargés à la main."""

import datetime as dt
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "p": "http://schemas.openxmlformats.org/package/2006/relationships"}
DATES, MONTANTS, LIBELLES = ("תאריך", "date"), ("סכום", "montant", "amount"), ("פריט הוצאה", "libellé", "libelle", "description")
SIGNATURES = ((b"%PDF", ".pdf"), (b"\xff\xd8\xff", ".jpg"), (b"\x89PNG", ".png"), (b"GIF8", ".gif"))


def colonne(ref):
    lettres = re.match(r"[A-Z]+", ref).group()
    n = 0
    for c in lettres:
        n = n * 26 + ord(c) - 64
    return n - 1


def lire(chemin):
    """[(date, montant, libellé, lien)] des lignes qui ont un lien (hyperlien ou adresse https:// écrite)."""
    z = zipfile.ZipFile(chemin)
    chaines = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            chaines.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    classeur = ET.fromstring(z.read("xl/workbook.xml"))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).findall("p:Relationship", NS)}
    resultat = []
    for feuille in classeur.find("m:sheets", NS):
        cible = rels[feuille.get("{%s}id" % NS["r"])].lstrip("/")
        cible = cible if cible.startswith("xl/") else "xl/" + cible
        racine = ET.fromstring(z.read(cible))
        liens = {}
        nom_rel = cible.replace("worksheets/", "worksheets/_rels/") + ".rels"
        if nom_rel in z.namelist():
            cibles = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read(nom_rel)).findall("p:Relationship", NS)}
            for h in racine.iter("{%s}hyperlink" % NS["m"]):
                adresse = cibles.get(h.get("{%s}id" % NS["r"]))
                if adresse and adresse.startswith("https://"):
                    liens[h.get("ref")] = adresse
        lignes = []
        for row in racine.iter("{%s}row" % NS["m"]):
            cellules = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS)
                if v is None:
                    continue
                cellules[c.get("r")] = chaines[int(v.text)] if c.get("t") == "s" else v.text
            lignes.append((row.get("r"), cellules))
        entete = None
        for numero, cellules in lignes[:6]:
            textes = {colonne(r): str(t or "").strip().lower() for r, t in cellules.items()}
            d = next((k for k, t in textes.items() if t in DATES), None)
            m = next((k for k, t in textes.items() if t in MONTANTS), None)
            if d is not None and m is not None:
                entete = (int(numero), d, m, next((k for k, t in textes.items() if t in LIBELLES), None))
                break
        if not entete:
            continue
        for numero, cellules in lignes:
            if int(numero) <= entete[0]:
                continue
            lien = next((liens[r] for r in cellules if r in liens), None) or \
                next((t for t in cellules.values() if isinstance(t, str) and t.startswith("https://")), None)
            if not lien:
                continue
            par_col = {colonne(r): t for r, t in cellules.items()}
            try:
                date = dt.date(1899, 12, 30) + dt.timedelta(days=int(float(par_col[entete[1]])))
                montant = abs(float(par_col[entete[2]]))
            except (KeyError, ValueError):
                continue
            resultat.append((date, montant, par_col.get(entete[3], "") if entete[3] is not None else "", lien))
    return resultat


def lire_csv(chemin):
    """Liste des liens en ligne exportée par ComptaJLC (« Liste des liens (CSV) ») : [(Mvt, lien)]."""
    import csv
    resultat = []
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            if (ligne.get("Lien") or "").startswith("https://"):
                resultat.append((int(ligne["Mvt"]), ligne["Lien"]))
    return resultat


def telecharger_csv(chemin):
    sortie = chemin.rsplit(".", 1)[0] + f"_Documents_{dt.date.today():%Y-%m-%d}.zip"
    echecs, rang = [], {}
    liens = lire_csv(chemin)
    print(f"{len(liens)} lien(s) trouvé(s).")
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for i, (mvt, lien) in enumerate(liens, 1):
            try:
                with urllib.request.urlopen(urllib.request.Request(lien, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
                    contenu = r.read()
            except Exception as e:
                echecs.append((mvt, lien, str(e)))
                print(f"  {i}/{len(liens)} Mvt {mvt} ÉCHEC {e}")
                continue
            ext = next((e for s, e in SIGNATURES if contenu.startswith(s)), None)
            if not ext:
                echecs.append((mvt, lien, "ce n'est ni un PDF ni une image (connexion demandée ?)"))
                print(f"  {i}/{len(liens)} Mvt {mvt} ÉCHEC : pas un document")
                continue
            rang[mvt] = rang.get(mvt, 0) + 1
            nom = f"{mvt} document{'' if rang[mvt] == 1 else ' (%d)' % rang[mvt]}{ext}"       # « 21 document.pdf » : n° de Mvt en tête
            z.writestr(nom, contenu)
            print(f"  {i}/{len(liens)} {nom}")
    print(f"\nFichier prêt : {sortie}")
    for mvt, lien, raison in echecs:
        print(f"  NON TÉLÉCHARGÉ Mvt {mvt} : {lien} - {raison}")
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    chemin = sys.argv[1]
    if chemin.lower().endswith(".csv"):
        return telecharger_csv(chemin)
    lignes = lire(chemin)
    print(f"{len(lignes)} lien(s) trouvé(s).")
    sortie = chemin.rsplit(".", 1)[0] + f"_Documents_{dt.date.today():%Y-%m-%d}.zip"
    echecs, vus = [], set()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as z:
        for i, (date, montant, libelle, lien) in enumerate(lignes, 1):
            if lien in vus:
                continue
            vus.add(lien)
            try:
                with urllib.request.urlopen(urllib.request.Request(lien, headers={"User-Agent": "Mozilla/5.0"}), timeout=60) as r:
                    contenu = r.read()
            except Exception as e:
                echecs.append((lien, str(e)))
                print(f"  {i}/{len(lignes)} ÉCHEC {e}")
                continue
            ext = next((e for s, e in SIGNATURES if contenu.startswith(s)), None)
            if not ext:
                echecs.append((lien, "ce n'est ni un PDF ni une image (connexion demandée ?)"))
                print(f"  {i}/{len(lignes)} ÉCHEC : pas un document")
                continue
            libelle = re.sub(r"[^\w .-]+", " ", libelle).strip()[:50]
            nom = f"{date:%Y-%m-%d} {montant:.2f}".replace(".", ",") + (f" {libelle}" if libelle else "") + f" ({i}){ext}"
            z.writestr(nom, contenu)
            print(f"  {i}/{len(lignes)} {nom}")
    print(f"\nFichier prêt : {sortie}")
    if echecs:
        print(f"{len(echecs)} document(s) non téléchargés :")
        for lien, raison in echecs:
            print("  ", lien, "-", raison)
    return 0


if __name__ == "__main__":
    sys.exit(main())
