"""Lecture d'un export RImport.txt d'un autre logiciel de comptabilité (format « ##Transfert »).

Fichier texte Windows (latin-1), colonnes séparées par des tabulations, en sections :
##Section Dos (devise), ##Section Mvt (une ligne d'écriture par ligne), ##Section Tiers (compte, nom), ##Section Jnl
(code, intitulé, type N, T, A, V ou O).

Colonnes utiles d'une ligne Mvt (à partir de 0) : 0 n° de Mvt, 1 journal, 2 date, 3 compte, 4 libellé du compte,
5 montant, 6 sens D ou C, 8 libellé, 13 code Anal, 14 libellé Anal, 23 lettrage.

Les lignes sont rendues au format de Ecritures.xlsx : l'import passe par le même moteur (contrôles, doublons, comptes et
codes Anal créés). Les journaux absents du site sont créés d'après la section Jnl. Une ligne sans code Anal prend celui
d'une autre ligne du même compte, sinon 0BILAN pour un compte de bilan (classes 1 à 5)."""

import csv
import re
from collections import defaultdict
from pathlib import Path

ENTETE = b"##Transfert"
TYPES = {"N": "AN", "T": "BQ", "A": "HA", "V": "VT", "O": "OD"}


def est_rimport(contenu):
    """Contenu (octets) qui commence par ##Transfert."""
    return contenu[:len(ENTETE) + 3].lstrip(b"\xef\xbb\xbf").startswith(ENTETE)


def reconnait(chemin):
    """Fichier .txt qui commence par ##Transfert."""
    if Path(chemin).suffix.lower() != ".txt":
        return False
    try:
        with open(chemin, "rb") as f:
            return est_rimport(f.read(len(ENTETE) + 3))
    except OSError:
        return False


def _montant(s):
    return s.replace("\xa0", "").replace(" ", "").replace(",", ".")


def _anal(code):
    """Code Anal abîmé par une référence de cellule Excel collée (« 3LOISO120B12C », « 3LOISO120B12C120:N120 ») : on garde
    le code d'origine."""
    return re.sub(r"O\d+B\d+C(\d+:N\d+)?$", "", code.strip())


def sections(chemin):
    """{nom de section: [(n° de ligne du fichier, [colonnes])]}."""
    texte = Path(chemin).read_bytes().decode("latin-1").replace("\x90", "É")
    res, courante = defaultdict(list), None
    for n, ligne in enumerate(texte.splitlines(), 1):
        if ligne.startswith("##Section"):
            courante = (ligne.split("\t") + [""])[1].strip()
        elif ligne.strip() and not ligne.startswith("##"):
            res[courante].append((n, [c.strip() for c in next(csv.reader([ligne], delimiter="\t"))]))
    return res


def lire(chemin):
    """Lignes d'écritures [(n° de ligne, {colonne de Ecritures.xlsx: valeur})] ; chaque ligne porte aussi l'intitulé et le
    type de son journal (clés « Intitulé » et « Type », d'après la section Jnl)."""
    s = sections(chemin)
    journaux = {r[0]: (r[1] if len(r) > 1 else r[0], TYPES.get(r[2] if len(r) > 2 else "", "OD")) for _, r in s["Jnl"]}
    noms_tiers = {r[0]: r[1] for _, r in s["Tiers"] if len(r) > 1 and r[1]}
    anal_du_compte = {}                    # code Anal d'un compte, pris sur ses lignes qui en portent un
    for _, r in s["Mvt"]:
        if len(r) > 13 and r[13]:
            anal_du_compte.setdefault(r[3], (_anal(r[13]), r[14] if len(r) > 14 else ""))
    lignes = []
    for n, r in s["Mvt"]:
        r = r + [""] * (24 - len(r))
        sens, montant = r[6].upper(), _montant(r[5])
        intitule, type_ = journaux.get(r[1], (r[1], "OD"))
        anal, libel_anal = (_anal(r[13]), r[14]) if r[13] else anal_du_compte.get(r[3], ("", ""))
        if not anal and r[3][:1] in "12345":           # compte de bilan sans code Anal
            anal, libel_anal = "0BILAN", "BILAN"
        lignes.append((n, {"Mvt": r[0], "Jnl": r[1], "Date": r[2], "Compte": r[3],
                           "LibelCompte": (noms_tiers.get(r[3]) or r[4])[:100], "Libelle": (r[8] or r[4])[:200],
                           "Debit": montant if sens == "D" else None, "Credit": montant if sens == "C" else None,
                           "Anal": anal, "LibelAnal": libel_anal[:100], "Lien": None, "Let": r[23] or None,
                           "Intitulé": intitule[:60], "Type": "AN" if r[1] == "AN" else type_}))
    return lignes
