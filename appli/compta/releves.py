"""Relevés bancaires : lecture (CSV, Excel, PDF Mizrahi en hébreu), import sans doublon,
rapprochement automatique et manuel, état de rapprochement (cahier des charges, Lot 3)."""

import csv
import datetime as dt
import io
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from .models import ZERO, Ligne, LigneReleve, ParametreReleve, Rapprochement, Reglage, soldes

HEBREU = re.compile(r"[֐-׿]")
INVISIBLES = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮"))

# en-têtes reconnus → colonne ; l'hébreu suit la requête Power Query du classeur
ENTETES = [
    ("valeur", ["ערך", "date valeur"]),
    ("date", ["תאריך", "date"]),
    ("operation", ["סוג", "opération", "operation", "תיאור"]),
    ("credit", ["זכות", "crédit", "credit"]),
    ("debit", ["חובה", "débit", "debit"]),
    ("montant", ["montant", "סכום"]),
    ("solde", ["יתרה", "solde"]),
    ("reference", ["אסמכתה", "référence", "reference"]),
]
MOTS_HEBREU = [m for _, ms in ENTETES for m in ms if HEBREU.search(m)]


def texte(v):
    return "" if v is None else str(v).translate(INVISIBLES).strip()


def colonne(entete):
    e = texte(entete).lower()
    for nom, mots in ENTETES:
        for m in mots:
            if m in e or m in e[::-1]:
                return nom
    return None


def nombre(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v)).quantize(Decimal("0.01"))
    s = texte(v).replace("₪", "").replace("\xa0", "").replace(" ", "")
    negatif = s.endswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()") if negatif else s
    if "," in s and "." in s:            # 1.234,56 ou 1,234.56
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".") if len(s.split(",")[-1]) == 2 else s.replace(",", "")
    try:
        n = Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return -n if negatif else n


def date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    s = texte(v)
    for f in ("%d/%m/%Y", "%d/%m/%y", "%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def normaliser(rangees):
    """Rangées brutes (listes de cellules) → lignes {date, reference, operation, montant, solde}.

    Cherche la ligne d'en-tête ; accepte un montant signé ou deux colonnes crédit / débit ;
    remet le texte hébreu à l'endroit s'il a été lu à l'envers (PDF)."""
    lignes, cols, inverse = [], None, False
    for r in rangees:
        cellules = [texte(c) for c in r]
        noms = [colonne(c) for c in cellules]
        if "date" in noms and ("montant" in noms or "credit" in noms or "debit" in noms):
            cols = noms
            inverse = any(h[::-1] in c and h not in c for c in cellules for h in MOTS_HEBREU)
            continue
        if not cols:
            continue
        v = {n: r[i] for i, n in enumerate(cols) if n and i < len(r)}
        d = date(v.get("date"))
        if v.get("montant") not in (None, ""):
            m = nombre(v.get("montant"))
        else:
            c, db = nombre(v.get("credit")), nombre(v.get("debit"))
            m = None if c is None and db is None else (c or ZERO) - abs(db or ZERO)
        if d is None or m is None or m == 0:
            continue
        op = texte(v.get("operation"))
        if inverse and HEBREU.search(op):
            op = op[::-1]
        lignes.append({"date": d, "reference": texte(v.get("reference"))[:40], "operation": op[:200], "montant": m,
                       "solde": nombre(v.get("solde"))})
    # ordre chronologique, ordre du relevé conservé dans la journée
    if len(lignes) > 1 and lignes[0]["date"] > lignes[-1]["date"]:
        lignes.reverse()
    lignes.sort(key=lambda l: l["date"])
    return lignes


def lire(nom, contenu):
    """Lit un fichier de relevé (octets) selon son extension."""
    ext = nom.lower().rsplit(".", 1)[-1]
    if ext == "csv":
        s = contenu.decode("utf-8-sig", errors="replace")
        sep = ";" if s.count(";") >= s.count(",") else ","
        return normaliser(list(csv.reader(io.StringIO(s), delimiter=sep)))
    if ext in ("xlsx", "xlsm"):
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(contenu), data_only=True, read_only=True)
        return normaliser([list(r) for ws in wb.worksheets for r in ws.iter_rows(values_only=True)])
    if ext == "pdf":
        import pdfplumber
        rangees = []
        with pdfplumber.open(io.BytesIO(contenu)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})
                for t in tables:
                    rangees += t
        return normaliser(rangees)
    raise ValueError("Format non reconnu : fichier .pdf, .xlsx ou .csv attendu.")


@transaction.atomic
def importer(journal, lignes, source="", solde_ouverture=None):
    """Ajoute les lignes absentes (clé : date, référence, montant, rang dans la journée).

    Renvoie (ajoutées, doublons, écarts de solde)."""
    rangs = defaultdict(int)
    existant = set(LigneReleve.objects.filter(journal=journal).values_list("date", "reference", "montant", "rang"))
    premiere = not LigneReleve.objects.filter(journal=journal).exists()
    nouvelles, doublons = [], 0
    for l in lignes:
        rangs[l["date"]] += 1
        cle = (l["date"], l["reference"], l["montant"], rangs[l["date"]])
        if cle in existant:
            doublons += 1
            continue
        nouvelles.append(LigneReleve(journal=journal, rang=rangs[l["date"]], source=source[:120], **l))
    if premiere and nouvelles:
        if solde_ouverture is None and nouvelles[0].solde is not None:
            solde_ouverture = nouvelles[0].solde - nouvelles[0].montant
        if solde_ouverture is None:
            raise ValueError("Premier relevé de ce compte : indiquer le solde d'ouverture.")
        veille = nouvelles[0].date - dt.timedelta(days=1)
        LigneReleve.objects.create(journal=journal, date=veille, rang=0, operation="Solde d'ouverture", montant=solde_ouverture,
                                   solde=solde_ouverture, ouverture=True, source=source[:120])
    LigneReleve.objects.bulk_create(nouvelles)
    return len(nouvelles), doublons, len(ecarts_solde(journal))


def ecarts_solde(journal):
    """Lignes dont le solde indiqué diffère du solde recalculé."""
    cumul, res = ZERO, []
    for l in LigneReleve.objects.filter(journal=journal):
        cumul += l.montant
        if l.solde is not None and abs(l.solde - cumul) >= Decimal("0.01"):
            res.append((l, cumul))
    return res


# ---------------------------------------------------------------- rapprochement

def tolerance():
    try:
        return int(Reglage.lire("tolerance_rapprochement", "7"))
    except ValueError:
        return 7


def date_reprise(journal):
    p = ParametreReleve.objects.filter(journal=journal).first()
    return p.date_reprise if p else None


def ecritures(journal):
    """Lignes d'écritures du compte de trésorerie du journal, à partir de la date de reprise."""
    qs = (Ligne.objects.filter(compte=journal.compte).exclude(mouvement__origine="cloture")
          .select_related("mouvement", "mouvement__journal"))
    reprise = date_reprise(journal)
    return qs.filter(mouvement__date__gte=reprise) if reprise else qs


def sans_an(journal):
    """Écritures du compte, hors à-nouveaux de clôture (déjà contenus dans l'historique)."""
    return Ligne.objects.filter(compte=journal.compte).exclude(mouvement__origine="cloture")


def montant(ecriture):
    return ecriture.debit - ecriture.credit


@transaction.atomic
def pointer(journal, releves, lignes, utilisateur=None, mode="manuel"):
    releves, lignes = list(releves), list(lignes)
    if not releves or not lignes:
        raise ValueError("Choisir au moins une ligne du relevé et une écriture.")
    if any(r.rapprochement_id for r in releves) or any(l.rapprochement_id for l in lignes):
        raise ValueError("Une des lignes choisies est déjà pointée.")
    total_r, total_e = sum(r.montant for r in releves), sum(montant(l) for l in lignes)
    if total_r != total_e:
        raise ValueError(f"Totaux différents : relevé {total_r} ₪, écritures {total_e} ₪.")
    r = Rapprochement.objects.create(journal=journal, mode=mode, cree_par=utilisateur)
    LigneReleve.objects.filter(pk__in=[x.pk for x in releves]).update(rapprochement=r)
    Ligne.objects.filter(pk__in=[x.pk for x in lignes]).update(rapprochement=r)
    return r


@transaction.atomic
def automatique(journal, utilisateur=None):
    """1) à-nouveau : solde d'ouverture du relevé et lignes antérieures à la reprise contre l'écriture de même total
    datée du jour de reprise ; 2) une ligne contre une écriture de même montant à ± tolérance jours (la plus proche)."""
    crees = 0
    ecr = list(ecritures(journal).filter(rapprochement__isnull=True))
    reprise = date_reprise(journal)
    if reprise:
        avant = list(LigneReleve.objects.filter(Q(date__lt=reprise) | Q(ouverture=True), journal=journal, rapprochement__isnull=True))
        total = sum((l.montant for l in avant), ZERO)
        an = next((e for e in ecr if e.mouvement.date == reprise and montant(e) == total), None)
        if avant and an:
            pointer(journal, avant, [an], utilisateur, "auto")
            ecr.remove(an)
            crees += 1
    tol = dt.timedelta(days=tolerance())
    libres = LigneReleve.objects.filter(journal=journal, rapprochement__isnull=True, ouverture=False)
    if reprise:
        libres = libres.filter(date__gte=reprise)
    for r in libres:
        candidats = [e for e in ecr if montant(e) == r.montant and abs(e.mouvement.date - r.date) <= tol]
        if candidats:
            e = min(candidats, key=lambda e: (abs(e.mouvement.date - r.date), e.mouvement.numero))
            pointer(journal, [r], [e], utilisateur, "auto")
            ecr.remove(e)
            crees += 1
    return crees


def depointer(rapprochement):
    rapprochement.releves.update(rapprochement=None)
    rapprochement.ecritures.update(rapprochement=None)
    rapprochement.delete()


def etat(journal, jusquau):
    """État de rapprochement à une date."""
    rel = LigneReleve.objects.filter(journal=journal, date__lte=jusquau)
    ecr = ecritures(journal).filter(mouvement__date__lte=jusquau)
    solde_releve = sum((l.montant for l in rel), ZERO)
    _, _, solde_compta = soldes(sans_an(journal).filter(mouvement__date__lte=jusquau))
    # pointé = rapproché avec des lignes toutes datées au plus tard à cette date
    hors = set(Rapprochement.objects.filter(Q(releves__date__gt=jusquau) | Q(ecritures__mouvement__date__gt=jusquau))
               .values_list("pk", flat=True))
    rel_np = [l for l in rel if l.rapprochement_id is None or l.rapprochement_id in hors]
    ecr_np = [e for e in ecr if e.rapprochement_id is None or e.rapprochement_id in hors]
    total_rel_np = sum((l.montant for l in rel_np), ZERO)
    total_ecr_np = sum((montant(e) for e in ecr_np), ZERO)
    return {
        "date": jusquau, "solde_releve": solde_releve, "solde_compta": solde_compta, "ecart": solde_releve - solde_compta,
        "releve_non_pointe": rel_np, "ecritures_non_pointees": ecr_np, "total_releve_np": total_rel_np, "total_ecr_np": total_ecr_np,
        "ecart_explique": (solde_releve - total_rel_np) - (solde_compta - total_ecr_np),
    }


def par_mois(journal):
    """Soldes de fin de mois relevé / compta et écart (comme l'onglet Banque1)."""
    rel = list(LigneReleve.objects.filter(journal=journal).values_list("date", "montant"))
    if not rel:
        return []
    reprise = date_reprise(journal)
    debut, fin = min(d for d, _ in rel), max(d for d, _ in rel)
    res, mois, precedent = [], dt.date(debut.year, debut.month, 1), None
    while mois <= fin:
        suivant = dt.date(mois.year + mois.month // 12, mois.month % 12 + 1, 1)
        fin_mois = min(suivant - dt.timedelta(days=1), fin)
        s_rel = sum((m for d, m in rel if d <= fin_mois), ZERO)
        s_cpt = ecart = variation = None
        if not reprise or fin_mois >= reprise:
            _, _, s_cpt = soldes(sans_an(journal).filter(mouvement__date__lte=fin_mois))
            ecart = s_rel - s_cpt
            variation = ecart - (precedent or ZERO)
            precedent = ecart
        res.append({"mois": mois, "releve": s_rel, "compta": s_cpt, "ecart": ecart, "variation": variation})
        mois = suivant
    return res
