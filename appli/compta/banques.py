"""Relevés tels que les banques les fournissent, convertis en lignes de la structure Banque (Journ, Date, Libelle, Debit,
Credit) : Crédit Mutuel (classeur « Vos comptes », une feuille par compte), Isracard (classeur des débits de cartes),
Revolut (relevé PDF, une partie par devise) et Mizrahi-Tefahot (relevé PDF des mouvements, en hébreu).

Chaque compte du relevé est relié à son journal par le réglage comptes_releves (« 00010982741=B1, 5524=I1,
732-204219=M1, REVOLUT EUR=R1 ») : numéro de compte Crédit Mutuel, 4 derniers chiffres de la carte, numéro de compte
Mizrahi, REVOLUT et la devise. Un compte du relevé sans journal est refusé, avec la clé à ajouter au réglage."""

import datetime as dt
import io
import re
from decimal import Decimal

from . import releves

MOIS = {"janv": 1, "févr": 2, "fevr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6, "juil": 7, "août": 8, "aout": 8,
        "sept": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12}
HEBREU = re.compile(r"[֐-׿]")


class Inconnu(Exception):
    """Comptes du relevé sans journal : clés à ajouter au réglage comptes_releves."""

    def __init__(self, cles):
        super().__init__(", ".join(cles))
        self.cles = cles


def correspondances():
    """{clé du relevé (majuscules): code du journal} d'après le réglage comptes_releves."""
    from .reglages import lire
    res = {}
    for x in re.split(r"[,;\n]", lire("comptes_releves")):
        if "=" in x:
            cle, jnl = x.split("=", 1)
            res[" ".join(cle.split()).upper()] = jnl.strip()
    return res


def _ligne(journal, date, libelle, montant):
    """Ligne de la structure Banque : montant positif = entrée (Credit), négatif = sortie (Debit)."""
    return {"Journ": journal, "Date": date, "Libelle": " ".join(libelle.split())[:200],
            "Debit": -montant if montant < 0 else None, "Credit": montant if montant > 0 else None}


def _par_journal(comptes):
    """comptes : [(clé, [(date, libellé, montant)])] → lignes Banque ; Inconnu si une clé (avec des lignes) n'a pas de journal."""
    table = correspondances()
    manquent = [cle for cle, mvts in comptes if mvts and cle.upper() not in table]
    if manquent:
        raise Inconnu(manquent)
    return [_ligne(table[cle.upper()], d, lib, m) for cle, mvts in comptes for d, lib, m in mvts if m]


# ---------------------------------------------------------------- classeurs

def credit_mutuel(wb):
    """Une feuille « Cpt … » par compte : ligne « R.I.B. : 10278 07395 00010982741 », puis Date, Valeur, Libellé, Débit, Crédit."""
    comptes = []
    for ws in wb.worksheets:
        rangees = list(ws.iter_rows(values_only=True))
        rib = next((str(r[0]) for r in rangees[:4] if r and str(r[0] or "").startswith("R.I.B.")), None)
        entete = next((i for i, r in enumerate(rangees[:10]) if r and [releves.texte(x) for x in r[:5]]
                       == ["Date", "Valeur", "Libellé", "Débit", "Crédit"]), None)
        if not rib or entete is None:
            continue
        mvts = []
        for r in rangees[entete + 1:]:
            date = releves.date(r[0])
            if not date:
                continue
            montant = (releves.nombre(r[4]) or Decimal(0)) - abs(releves.nombre(r[3]) or Decimal(0))
            mvts.append((date, releves.texte(r[2]), montant))
        comptes.append((rib.split()[-1], mvts))
    return comptes or None


def isracard(wb):
    """Débits de cartes (feuille « חיובים בשקלים ») : une partie par carte (« ארבע ספרות אחרונות 5524 »), puis
    תאריך חיוב, תאריך העסקה, בית העסק, סכום העסקה, סכום החיוב. Le montant débité est sorti du compte de la carte, à la
    date de l'achat."""
    comptes, carte = [], None
    for ws in wb.worksheets[:1]:
        for r in ws.iter_rows(values_only=True):
            premiere = releves.texte(r[0] if r else "")
            trouve = re.search(r"ארבע ספרות אחרונות\s*(\d{4})", premiere)
            if trouve:
                carte = trouve.group(1)
                comptes.append((carte, []))
                continue
            if carte and len(r) >= 5 and releves.date(r[1]) and releves.nombre(r[4]) is not None:
                comptes[-1][1].append((releves.date(r[1]), f"{releves.texte(r[2])} (carte {carte}, débit du {releves.texte(r[0])})",
                                       -releves.nombre(r[4])))
    return comptes or None


def depuis_classeur(contenu):
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(contenu), data_only=True)
    try:
        for lecteur in (credit_mutuel, isracard):
            comptes = lecteur(wb)
            if comptes:
                return comptes
    finally:
        wb.close()
    return None


# ---------------------------------------------------------------- PDF

def _texte_pdf(contenu):
    from pypdf import PdfReader
    return "\n".join(p.extract_text(extraction_mode="layout") for p in PdfReader(io.BytesIO(contenu)).pages)


def _montant(s):
    return Decimal(re.sub(r"[\s  ]", "", s).replace(",", "."))


MONTANT_REVOLUT = r"(?<![\w,])(-?(?:\d{1,3}(?:[   ]\d{3})+|\d+),\d\d)\s?[€₪$£]"     # « 1 234,56€ », jamais « N1  9,40€ »


def revolut(texte):
    """Une partie par devise (« Relevé EUR ») : solde d'ouverture au résumé, mouvements « 1 nov. 2026  Libellé  montant
    solde » ; le sens vient de la variation du solde. Les opérations « En attente » ne sont pas reprises."""
    comptes, devise, solde, attente = {}, None, None, False
    for ligne in texte.splitlines():
        s = ligne.strip()
        if re.fullmatch(r"Relevé [A-Z]{3}", s):
            if s[-3:] != devise:
                devise = s[-3:]
                comptes.setdefault(devise, [])
                solde = None
            continue
        if s.startswith(("En attente", "Renvoyé")):          # opérations en attente ou renvoyées : hors solde
            attente = True
        elif s.startswith("Transactions du compte"):
            attente = False
        montants = re.findall(MONTANT_REVOLUT, s)
        if s.startswith("Compte (") and montants and solde is None:
            solde = _montant(montants[0])                       # solde d'ouverture
            continue
        date = re.match(r"(\d{1,2}) ([a-zéû]+)\.? (\d{4})\s{2,}(.+?)\s{2,}", s)
        if not devise or attente or not date or len(montants) != 2 or date.group(2)[:4].rstrip(".") not in MOIS:
            continue
        montant, nouveau = _montant(montants[0]), _montant(montants[1])
        if solde is not None and abs(abs(nouveau - solde) - montant) < Decimal("0.01"):
            montant = nouveau - solde
        else:                                               # sans solde précédent : colonne « Argent sortant » ou « entrant »
            montant = -montant if ligne.find(montants[0]) < len(ligne) * 0.62 else montant
        solde = nouveau
        jour = dt.date(int(date.group(3)), MOIS[date.group(2)[:4].rstrip(".")], int(date.group(1)))
        comptes[devise].append((jour, date.group(4), montant))
    return [(f"REVOLUT {d}", m) for d, m in comptes.items()] or None


def _hebreu(texte):
    """Texte hébreu extrait du PDF dans l'ordre visuel : mots dans l'ordre de lecture, lettres remises à l'endroit."""
    mots = texte.split()
    mots.reverse()
    sym = str.maketrans("()[]", ")(][")
    return " ".join(m[::-1].translate(sym) if HEBREU.search(m) else m for m in mots)


def mizrahi(texte):
    """Mouvements du compte (« חשבון מספר 732-204219 ») : référence, [solde], montant signé, libellé, date jj/mm/aa."""
    compte = re.search(r"(\d{3}-\d{4,})", texte)
    if not compte or not HEBREU.search(texte):
        return None
    mvts = []
    for ligne in texte.splitlines():
        m = re.match(r"\s*\d+\s+(?:-?[\d,]+\.\d\d\s+)?(-?[\d,]+\.\d\d)\s+(.+?)\s+(\d\d/\d\d/\d\d)\s*$", ligne)
        if m:
            mvts.append((dt.datetime.strptime(m.group(3), "%d/%m/%y").date(), _hebreu(m.group(2)),
                         Decimal(m.group(1).replace(",", ""))))
    return [(compte.group(1), mvts)] if mvts else None


def depuis_pdf(contenu):
    texte = _texte_pdf(contenu)
    if "Revolut" in texte and "Relevé" in texte:
        return revolut(texte)
    return mizrahi(texte)


def convertir(nom, contenu):
    """Lignes Banque d'un relevé de banque reconnu ; None si le fichier n'est pas l'un de ces relevés."""
    suffixe = nom.lower().rsplit(".", 1)[-1]
    if suffixe == "pdf":
        comptes = depuis_pdf(contenu)
    elif suffixe in ("xlsx", "xlsm"):
        comptes = depuis_classeur(contenu)
    else:
        return None
    return _par_journal(comptes) if comptes else None
