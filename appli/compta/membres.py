"""Suivi des membres (cahier des charges, Lot 2) : situation, ancienneté des impayés, cotisations,
relance et lettrage des comptes de membres."""

import datetime as dt
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from .models import ZERO, Compte, Ligne, Membre, Modification, Reglage, TypeTiers

TRANCHES = [("0–30 j", 30), ("31–90 j", 90), ("> 90 j", None)]


def _cle_nom(nom):
    s = unicodedata.normalize("NFKD", nom.upper())
    return "".join(ch for ch in s if ch.isalpha() and ord(ch) < 128)[:5]


def compte_propose(nom, type_tiers=None):
    """Préfixe du type + 5 premières lettres du nom + rang : 411TAIEB001, 401PARTN001…"""
    t = type_tiers or TypeTiers.objects.filter(libelle="Membre").first()
    prefixe = (t.prefixe if t else "411") + _cle_nom(nom)
    rang = 1
    while Compte.objects.filter(numero=f"{prefixe}{rang:03d}").exists():
        rang += 1
    return f"{prefixe}{rang:03d}"


@transaction.atomic
def creer_tiers(type_tiers, nom, prenom="", **coordonnees):
    """Crée le compte (axe 1 repris d'un compte du même type) et la fiche du tiers."""
    libelle = f"{nom.strip().upper()} {prenom.strip().upper()}".strip()
    modele = Compte.objects.filter(numero__startswith=type_tiers.prefixe, anal1__isnull=False).first()
    compte = Compte.objects.create(numero=compte_propose(nom, type_tiers), libelle=libelle, lettrable=True,
                                   anal1=modele.anal1 if modele else None)
    Membre.objects.create(compte=compte, type=type_tiers, nom=nom.strip().upper(), prenom=prenom.strip(),
                          **{k: (v or "").strip() for k, v in coordonnees.items()})
    return compte


def type_du_compte(numero):
    """Type de tiers d'après le préfixe du compte (le plus long qui convient)."""
    types = sorted(TypeTiers.objects.all(), key=lambda t: -len(t.prefixe))
    return next((t for t in types if numero.startswith(t.prefixe)), None)


def creer_manquants():
    """Une fiche pour chaque compte de tiers (membres, fournisseurs…) ; les comptes collectifs de membres (tout en chiffres)
    sont exclus. Complète aussi le type des fiches qui n'en ont pas. Renvoie le nombre de fiches créées."""
    n = 0
    for t in TypeTiers.objects.all():
        for c in Compte.objects.filter(numero__startswith=t.prefixe, membre__isnull=True):
            if t.libelle == "Membre" and c.numero.isdigit():
                continue
            mots = c.libelle.split()
            if t.libelle == "Membre":
                Membre.objects.create(compte=c, type=t, nom=mots[0] if mots else c.libelle, prenom=" ".join(mots[1:]).title())
            else:
                Membre.objects.create(compte=c, type=t, nom=c.libelle)
            n += 1
    for m in Membre.objects.filter(type__isnull=True).select_related("compte"):
        m.type = type_du_compte(m.compte_id)
        if m.type:
            m.save(update_fields=["type"])
    return n


# ---------------------------------------------------------------- situation d'un compte de membre

@dataclass
class Situation:
    facture: Decimal = ZERO
    regle: Decimal = ZERO
    solde: Decimal = ZERO
    impayes: list = field(default_factory=list)       # (ligne, restant dû, jours)
    tranches: list = field(default_factory=list)      # (libellé, montant)
    avance: Decimal = ZERO


def allouer(lignes):
    """Règlements (crédits) imputés sur les factures (débits) les plus anciennes ; renvoie [(ligne débit, restant)] et l'avance."""
    debits = [[l, l.debit] for l in lignes if l.debit > 0]
    credit = sum((l.credit for l in lignes), ZERO)
    for d in debits:
        pris = min(d[1], credit)
        d[1] -= pris
        credit -= pris
    return [(l, r) for l, r in debits if r > 0], credit


def situation(compte, jusquau=None):
    jusquau = jusquau or dt.date.today()
    ls = list(Ligne.objects.filter(compte=compte, mouvement__date__lte=jusquau).exclude(mouvement__origine="cloture")
              .select_related("mouvement").order_by("mouvement__date", "mouvement__numero", "ordre"))
    s = Situation(facture=sum((l.debit for l in ls), ZERO), regle=sum((l.credit for l in ls), ZERO))
    s.solde = s.facture - s.regle
    restants, s.avance = allouer([l for l in ls if not l.lettrage])
    s.impayes = [(l, r, (jusquau - l.mouvement.date).days) for l, r in restants]
    bornes = []
    for lib, jours in TRANCHES:
        bas = bornes[-1] if bornes else -1
        bornes.append(jours if jours is not None else 10 ** 6)
        s.tranches.append((lib, sum((r for _, r, j in s.impayes if bas < j <= bornes[-1]), ZERO)))
    return s


def impayes(jusquau=None):
    """Membres avec un solde dû, du plus gros au plus petit."""
    res = []
    for m in Membre.objects.select_related("compte"):
        s = situation(m.compte, jusquau)
        if s.solde > 0:
            res.append((m, s))
    return sorted(res, key=lambda x: -x[1].solde)


def cotisations(exercice):
    """Cotisations de l'exercice par membre : attendue (membre actif), facturée, reçue, restant dû."""
    compte_cot = Reglage.lire("compte_cotisations")
    res = []
    for m in Membre.objects.filter(type__libelle="Membre").select_related("compte"):
        mvts = Ligne.objects.filter(compte=m.compte, debit__gt=0, mouvement__date__range=(exercice.debut, exercice.fin)).values("mouvement")
        cot = Ligne.objects.filter(mouvement__in=mvts, compte_id=compte_cot)
        facturee = sum((l.credit - l.debit for l in cot), ZERO)
        s = situation(m.compte, exercice.fin)
        du = sum((r for l, r, _ in s.impayes if l.mouvement.date >= exercice.debut
                  and l.mouvement.lignes.filter(compte_id=compte_cot).exists()), ZERO)
        attendue = (m.cotisation or ZERO) if m.statut == "actif" else ZERO
        if attendue or facturee:
            res.append({"membre": m, "attendue": attendue, "facturee": facturee, "recue": facturee - du, "du": du})
    tot = {k: sum((r[k] for r in res), ZERO) for k in ("attendue", "facturee", "recue", "du")}
    tot["taux"] = round(tot["recue"] * 100 / tot["facturee"], 1) if tot["facturee"] else None
    tot["compte"] = compte_cot
    return res, tot


# ---------------------------------------------------------------- relance

TEXTE_RELANCE = """Bonjour {prenom} {nom},

Sauf erreur de notre part, votre compte auprès de la Loge Bnei Brith présente un solde dû de {montant} :

{detail}

Nous vous remercions de bien vouloir régulariser ce montant, ou de nous signaler toute erreur.

Bien cordialement,
Le trésorier"""


def texte_relance(membre, s):
    modele = Reglage.lire("texte_relance") or TEXTE_RELANCE
    detail = "\n".join(f"- {l.mouvement.date:%d/%m/%Y} {l.libelle} : {montant(r)}" for l, r, _ in s.impayes)
    return modele.format(prenom=membre.prenom, nom=membre.nom.title(), montant=montant(s.solde), detail=detail)


def montant(v):
    return f"{v:,.2f}".replace(",", " ").replace(".", ",") + " ₪"


# ---------------------------------------------------------------- lettrage

def code_suivant(compte):
    """A, B, … Z, AA, AB… : premier code libre du compte."""
    pris = set(Ligne.objects.filter(compte=compte).exclude(lettrage="").values_list("lettrage", flat=True))
    n = 0
    while True:
        code, k = "", n
        while True:
            code = chr(65 + k % 26) + code
            k = k // 26 - 1
            if k < 0:
                break
        if code not in pris:
            return code
        n += 1


@transaction.atomic
def lettrer(compte, lignes, auteur=""):
    lignes = list(lignes)
    if len(lignes) < 2 or any(l.compte_id != compte.numero or l.lettrage for l in lignes):
        raise ValueError("Choisir au moins deux lignes non lettrées de ce compte.")
    d, c = sum((l.debit for l in lignes), ZERO), sum((l.credit for l in lignes), ZERO)
    if d != c:
        raise ValueError(f"Débit {montant(d)} ≠ crédit {montant(c)} : le lettrage doit être équilibré.")
    code = code_suivant(compte)
    Ligne.objects.filter(pk__in=[l.pk for l in lignes]).update(lettrage=code)
    if auteur:
        Modification.objects.create(auteur=auteur, lot="Membres", action="Lettrage", objet=f"compte {compte.numero}",
                                    apres=f"{code} : {len(lignes)} lignes, {montant(d)}")
    return code


@transaction.atomic
def delettrer(compte, code, auteur=""):
    n = Ligne.objects.filter(compte=compte, lettrage=code).update(lettrage="")
    if n and auteur:
        Modification.objects.create(auteur=auteur, lot="Membres", action="Délettrage", objet=f"compte {compte.numero}", avant=code)
    return n


def lettrage_automatique(compte, auteur=""):
    """1) facture et règlement de même montant dans un même mouvement ; 2) facture puis premier règlement
    ultérieur de même montant. Renvoie le nombre de lettrages."""
    ls = list(Ligne.objects.filter(compte=compte, lettrage="").exclude(mouvement__origine="cloture")
              .select_related("mouvement").order_by("mouvement__date", "mouvement__numero", "ordre"))
    libres = {l.pk: l for l in ls}
    paires = []
    for l in ls:
        if l.debit > 0 and l.pk in libres:
            meme = next((x for x in ls if x.pk in libres and x.mouvement_id == l.mouvement_id and x.credit == l.debit), None)
            if meme:
                paires.append((l, meme))
                del libres[l.pk], libres[meme.pk]
    for l in ls:
        if l.debit > 0 and l.pk in libres:
            suite = next((x for x in ls if x.pk in libres and x.credit == l.debit and x.mouvement.date >= l.mouvement.date), None)
            if suite:
                paires.append((l, suite))
                del libres[l.pk], libres[suite.pk]
    for a, b in paires:
        lettrer(compte, [a, b])
    if paires and auteur:
        Modification.objects.create(auteur=auteur, lot="Membres", action="Lettrage automatique", objet=f"compte {compte.numero}",
                                    apres=f"{len(paires)} lettrage(s)")
    return len(paires)


# ---------------------------------------------------------------- import du modèle 07_membres.csv

def cle(texte):
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower())


def importer_csv(rangees):
    """Met à jour (ou crée) les fiches à partir des colonnes du modèle Imports/modeles/07_membres.csv
    (Type, Adresse, Code postal et Ville sont facultatifs)."""
    from .releves import date as lire_date, nombre
    entetes, maj, inconnus = None, 0, []
    for r in rangees:
        if entetes is None:
            entetes = [cle(c) for c in r]
            continue
        v = dict(zip(entetes, r))
        compte = Compte.objects.filter(numero=(v.get("compte") or "").strip()).first()
        if not compte:
            if (v.get("compte") or "").strip():
                inconnus.append(v["compte"].strip())
            continue
        statut = cle(v.get("statut"))
        t = TypeTiers.objects.filter(libelle__iexact=(v.get("type") or "").strip()).first() or type_du_compte(compte.numero)
        texte = lambda k: (v.get(k) or "").strip()  # noqa: E731
        Membre.objects.update_or_create(compte=compte, defaults={
            "type": t, "nom": texte("nom").upper() or compte.libelle, "prenom": texte("prenom"),
            "adresse": texte("adresse"), "code_postal": texte("codepostal") or texte("cp"), "ville": texte("ville"),
            "telephone": texte("telephone"), "email": texte("email"),
            "date_adhesion": lire_date(v.get("datedadhesion")), "cotisation": nombre(v.get("cotisationannuelle")),
            "statut": statut if statut in dict(Membre.STATUTS) else "actif"})
        maj += 1
    return maj, inconnus
