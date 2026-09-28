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

from .models import ZERO, Ligne, LigneReleve, Modification, Mouvement, ParametreReleve, Rapprochement, Reglage, soldes

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


DATE_COURTE = re.compile(r"^\d\d/\d\d/\d\d(\d\d)?$")
NOMBRE = re.compile(r"^₪?-?[\d,]+\.\d\d-?$")
MIROIR = str.maketrans("()<>", ")(><")


def _logique(mot):
    """Mot hébreu lu dans l'ordre visuel (PDF) → ordre logique ; les chiffres restent dans leur sens."""
    return mot[::-1].translate(MIROIR) if HEBREU.search(mot) else mot


def lire_pdf_mizrahi(contenu):
    """Relevé PDF du site Mizrahi-Tefahot (עובר ושב - יתרה ותנועות בחשבון), lu par la position des mots.

    Colonnes repérées sur la ligne d'en-tête de chaque page. Le solde, imprimé seulement sur la dernière ligne
    de chaque date, est complété depuis le solde d'ouverture (יתרה קודמת) et vérifié contre les soldes imprimés.
    Renvoie [] si le document n'a pas cette mise en page."""
    import pdfplumber
    lignes, ouverture = [], None
    with pdfplumber.open(io.BytesIO(contenu)) as pdf:
        for page in pdf.pages:
            mots = [dict(m, texte=_logique(m["text"])) for m in page.extract_words()]
            rangs = defaultdict(list)
            for m in mots:
                rangs[round(m["top"] / 3)].append(m)
            entete = next((r for r in rangs.values() if any(m["texte"] == "אסמכתה" for m in r)), None)
            if not entete:
                continue
            x = lambda cond: max((m["x1"] for m in entete if cond(m["texte"])), default=None)  # noqa: E731
            dates = sorted(m["x1"] for m in entete if m["texte"] == "תאריך")      # date, puis date de valeur
            cols = {"date": dates[-1] if dates else None, "valeur": dates[0] if len(dates) > 1 else None, "montant": x(lambda t: "זכות" in t),
                    "solde": x(lambda t: t in ("יתרה", 'בש"ח')), "reference": x(lambda t: t == "אסמכתה")}
            if None in cols.values():
                continue
            haut = min(m["top"] for m in entete)
            proche = lambda m, c: abs(m["x1"] - cols[c]) <= 15  # noqa: E731
            for cle in sorted(rangs):
                r = rangs[cle]
                if any(m["texte"] == "קודמת" for m in r):                            # יתרה קודמת : solde d'ouverture
                    v = next((m["texte"] for m in r if m["texte"].startswith("₪")), None)
                    ouverture = nombre(v) if v else ouverture
                    continue
                if min(m["top"] for m in r) <= haut:
                    continue
                d = next((m for m in r if proche(m, "date") and DATE_COURTE.match(m["texte"])), None)
                if not d:
                    continue
                l = {"date": date(d["texte"]), "reference": "", "montant": None, "solde": None}
                texte = []
                for m in r:
                    t = m["texte"]
                    if m is d or (proche(m, "valeur") and DATE_COURTE.match(t)) or t in ("<", ">"):
                        continue
                    if NOMBRE.match(t) and proche(m, "montant"):
                        l["montant"] = nombre(t)
                    elif NOMBRE.match(t) and proche(m, "solde"):
                        l["solde"] = nombre(t)
                    elif t.isdigit() and proche(m, "reference"):
                        l["reference"] = t
                    else:
                        texte.append(m)
                l["operation"] = " ".join(m["texte"] for m in sorted(texte, key=lambda m: -m["x1"]))[:200]
                if l["montant"] is not None:
                    lignes.append(l)
    if lignes and ouverture is not None:
        cumul = ouverture
        for l in lignes:
            cumul += l["montant"]
            if l["solde"] is not None and l["solde"] != cumul:
                raise ValueError(f"Relevé incohérent le {l['date']:%d/%m/%Y} : solde imprimé {l['solde']}, solde recalculé {cumul}.")
            l["solde"] = cumul
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
        lignes = lire_pdf_mizrahi(contenu)
        if lignes:
            return lignes
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


# ---------------------------------------------------------------- écriture créée depuis une ligne du relevé

def a_affecter(journal):
    """Lignes téléchargées sans écriture (non reliées), à partir de la date de reprise."""
    qs = LigneReleve.objects.filter(journal=journal, rapprochement__isnull=True, ouverture=False)
    reprise = date_reprise(journal)
    return (qs.filter(date__gte=reprise) if reprise else qs).order_by("date", "rang", "pk")


def deja_en_compta(l):
    """Écritures de banque non reliées, de même montant, à ± tolérance jours : la ligne est peut-être déjà saisie."""
    ecart = dt.timedelta(days=tolerance())
    qs = ecritures(l.journal).filter(rapprochement__isnull=True, mouvement__date__range=(l.date - ecart, l.date + ecart))
    qs = qs.filter(debit=l.montant, credit=ZERO) if l.montant > 0 else qs.filter(credit=-l.montant, debit=ZERO)
    return list(qs.order_by("mouvement__date", "mouvement__numero"))


def pistes(l, jours=60):
    """Quand rien n'est proposé : pourquoi ? Écritures de même montant hors du cadre habituel.

    loin : non reliées, sur le compte de la banque, à plus de « tolérance » jours (jusqu'à 60) : reliables ;
    reliees : déjà reliées à une autre ligne du relevé (relevé importé deux fois ?) ;
    ailleurs : sur un autre compte de trésorerie (5…) à tolérance près : saisies sur la mauvaise banque ?"""
    ecart, large = dt.timedelta(days=tolerance()), dt.timedelta(days=jours)
    montant = (dict(debit=l.montant, credit=ZERO) if l.montant > 0 else dict(credit=-l.montant, debit=ZERO))
    proches = ecritures(l.journal).filter(mouvement__date__range=(l.date - large, l.date + large), **montant)
    loin = [e for e in proches.filter(rapprochement__isnull=True).order_by("mouvement__date")
            if abs((e.mouvement.date - l.date).days) > ecart.days]
    reliees = []
    for e in proches.filter(rapprochement__isnull=False).order_by("mouvement__date")[:3]:
        autre = LigneReleve.objects.filter(rapprochement_id=e.rapprochement_id).exclude(pk=l.pk).first()
        reliees.append((e, autre))
    ailleurs = list(Ligne.objects.filter(compte__numero__startswith="5", mouvement__date__range=(l.date - ecart, l.date + ecart),
                                         rapprochement__isnull=True, **montant)
                    .exclude(compte=l.journal.compte).exclude(mouvement__origine="cloture")
                    .select_related("mouvement", "compte")[:3])
    return {"loin": loin[:3], "reliees": reliees, "ailleurs": ailleurs}


def libelle_releve(l):
    t = l.traduction
    return (t if t != "À traduire" else l.operation)[:60].upper()


@transaction.atomic
def creer_ecriture(l, compte, anal2, utilisateur=None, forcer=False):
    """Un Mvt à deux lignes (banque / contrepartie, même code axe 2), aussitôt relié à la ligne du relevé.

    Refus si la ligne est déjà reliée (pas de double écriture) ou si une écriture identique existe déjà en compta
    (sauf forcer=True)."""
    l = LigneReleve.objects.select_for_update().select_related("journal__compte").get(pk=l.pk)
    if l.rapprochement_id or l.ouverture:
        raise ValueError("Cette ligne a déjà son écriture.")
    banque = l.journal.compte
    if compte.pk == banque.pk:
        raise ValueError("La contrepartie ne peut pas être le compte de la banque elle-même.")
    if not forcer and deja_en_compta(l):
        raise ValueError("Une écriture de même montant existe déjà à une date proche : reliez-la, ou cochez « nouvelle ».")
    m = abs(l.montant)
    mv = Mouvement.objects.create(numero=Mouvement.prochain_numero(), date=l.date, journal=l.journal,
                                  piece=Mouvement.prochaine_piece(), origine="saisie", cree_par=utilisateur,
                                  commentaire=f"Relevé {l.journal.code} du {l.date:%d/%m/%Y} : {l.operation}")
    lib = libelle_releve(l)
    entree = l.montant > 0
    ligne_banque = Ligne.objects.create(mouvement=mv, ordre=1, compte=banque, libelle=lib, anal2=anal2,
                                        debit=m if entree else ZERO, credit=ZERO if entree else m)
    Ligne.objects.create(mouvement=mv, ordre=2, compte=compte, libelle=lib, anal2=anal2,
                         debit=ZERO if entree else m, credit=m if entree else ZERO)
    pointer(l.journal, [l], [ligne_banque], utilisateur, "saisie")
    Modification.objects.create(auteur=utilisateur.get_username() if utilisateur else "", lot="Banque",
                                action="Écriture depuis le relevé", objet=f"Mvt {mv.numero}",
                                apres=f"{l.journal.code} {l.date:%d/%m/%Y} {l.montant} ; {compte.pk} ; {anal2.pk}")
    return mv


def relier(l, ecriture, utilisateur=None):
    """La ligne du relevé est déjà en compta : on la relie à cette écriture (aucune écriture créée)."""
    return pointer(l.journal, [l], [ecriture], utilisateur, "manuel")
