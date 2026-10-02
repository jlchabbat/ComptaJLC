"""Relevés bancaires : import sans doublon (structure unique, voir echanges.imp_banque_tout),
rapprochement automatique et manuel, état de rapprochement (cahier des charges, Lot 3)."""

import datetime as dt
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q

from .models import ZERO, ImportReleve, Ligne, LigneReleve, Modification, Mouvement, ParametreReleve, Rapprochement, Reglage, soldes
from .reglages import montant as en_devise

INVISIBLES = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮"))


def texte(v):
    return "" if v is None else str(v).translate(INVISIBLES).strip()


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
    for f in ("%d/%m/%Y", "%d/%m/%y", "%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def _libelle_cle(texte):
    return " ".join((texte or "").split())


@transaction.atomic
def importer(journal, lignes, source="", solde_ouverture=None, auteur=""):
    """Ajoute les lignes absentes. Clé : date, libellé de la banque et montant (journal compris) ; deux lignes
    identiques le même jour comptent pour deux (la 2e du fichier retrouve la 2e de la base).

    Renvoie (ajoutées, doublons, écarts de solde)."""
    en_base = defaultdict(int)
    dernier_rang = defaultdict(int)
    for date, operation, montant, rang in LigneReleve.objects.filter(journal=journal, ouverture=False).values_list(
            "date", "operation", "montant", "rang"):
        en_base[(date, _libelle_cle(operation), montant)] += 1
        dernier_rang[date] = max(dernier_rang[date], rang)
    premiere = not LigneReleve.objects.filter(journal=journal).exists()
    vus, nouvelles, doublons = defaultdict(int), [], 0
    carte = any(l.pop("carte", False) for l in lignes)
    if carte and solde_ouverture is None:
        solde_ouverture = ZERO                            # relevé de carte (Isracard…) : pas de solde, débité chaque mois
    for l in lignes:
        cle = (l["date"], _libelle_cle(l["operation"]), l["montant"])
        vus[cle] += 1
        if vus[cle] <= en_base[cle]:                      # n-ième ligne identique déjà en base
            doublons += 1
            continue
        dernier_rang[l["date"]] += 1                      # après les lignes déjà en base du même jour
        nouvelles.append(LigneReleve(journal=journal, rang=dernier_rang[l["date"]], source=source[:120], **l))
    if premiere and nouvelles:
        if solde_ouverture is None and nouvelles[0].solde is not None:
            solde_ouverture = nouvelles[0].solde - nouvelles[0].montant
        if solde_ouverture is None:
            raise ValueError("Premier relevé de ce compte : indiquer le solde d'ouverture.")
        veille = nouvelles[0].date - dt.timedelta(days=1)
        LigneReleve.objects.create(journal=journal, date=veille, rang=0, operation="Solde d'ouverture", montant=solde_ouverture,
                                   solde=solde_ouverture, ouverture=True, source=source[:120])
    LigneReleve.objects.bulk_create(nouvelles)
    ImportReleve.objects.create(journal=journal, fichier=source[:200], ajoutees=len(nouvelles), doublons=doublons, auteur=auteur[:100])
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
    """Montant signé de l'écriture, comparé à celui du relevé (débit positif)."""
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
        raise ValueError(f"Totaux différents : relevé {en_devise(total_r)}, écritures {en_devise(total_e)}.")
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
    qs = LigneReleve.objects.filter(journal=journal, rapprochement__isnull=True, ouverture=False, ecartee=False)
    reprise = date_reprise(journal)
    return (qs.filter(date__gte=reprise) if reprise else qs).order_by("date", "rang", "pk")


def ecartees(journal):
    """Lignes écartées à la main : ni écriture ni lien, retirées de la liste à affecter."""
    return LigneReleve.objects.filter(journal=journal, rapprochement__isnull=True, ecartee=True).order_by("date", "rang", "pk")


def deja_en_compta(l):
    """Écritures de banque non reliées, de même montant, à ± tolérance jours : la ligne est peut-être déjà saisie."""
    ecart = dt.timedelta(days=tolerance())
    qs = ecritures(l.journal).filter(rapprochement__isnull=True, mouvement__date__range=(l.date - ecart, l.date + ecart))
    qs = qs.filter(debit=l.montant, credit=ZERO) if l.montant > 0 else qs.filter(credit=-l.montant, debit=ZERO)
    return list(qs.order_by("mouvement__date", "mouvement__numero"))


def groupes(l, maxi=4):
    """Plusieurs écritures non reliées dont la somme fait la ligne du relevé (prélèvement de carte, remise de chèques…),
    à ± tolérance jours : [(écritures), …], les plus proches de la date d'abord (3 au plus)."""
    from itertools import combinations
    ecart = dt.timedelta(days=tolerance())
    sens = dict(debit__gt=0, credit=ZERO) if l.montant > 0 else dict(credit__gt=0, debit=ZERO)
    cibles = sorted(ecritures(l.journal).filter(rapprochement__isnull=True, mouvement__date__range=(l.date - ecart, l.date + ecart),
                                                **sens),
                    key=lambda e: (abs((e.mouvement.date - l.date).days), e.mouvement.numero))[:14]
    trouves = []
    for n in range(2, maxi + 1):
        for combi in combinations(cibles, n):
            if sum(montant(e) for e in combi) == l.montant:
                trouves.append(combi)
                if len(trouves) >= 3:
                    return trouves
    return trouves


def lignes_groupees(l, maxi=4):
    """Plusieurs lignes du relevé (dont l) pour une seule écriture non reliée : frais du mois passés en une fois.
    [(lignes du relevé, écriture), …] (3 au plus), lignes et écriture à ± tolérance jours."""
    from itertools import combinations
    ecart = dt.timedelta(days=tolerance())
    autres = sorted(a_affecter(l.journal).filter(date__range=(l.date - ecart, l.date + ecart)).exclude(pk=l.pk),
                    key=lambda x: (abs((x.date - l.date).days), x.rang))[:10]
    cibles = {}
    for e in ecritures(l.journal).filter(rapprochement__isnull=True, mouvement__date__range=(l.date - ecart, l.date + ecart)):
        cibles.setdefault(montant(e), []).append(e)
    trouves = []
    for n in range(1, maxi):
        for combi in combinations(autres, n):
            total = l.montant + sum(x.montant for x in combi)
            for e in cibles.get(total, [])[:1]:
                trouves.append(((l,) + combi, e))
                if len(trouves) >= 3:
                    return trouves
    return trouves


def lignes_nulles(l, maxi=4):
    """Lignes du relevé (dont l) dont la somme est nulle (dépôt renouvelé : sortie, retour et intérêts), le même jour :
    elles se relient entre elles, sans écriture. Premier groupe trouvé, ou None."""
    from itertools import combinations
    autres = list(a_affecter(l.journal).filter(date=l.date).exclude(pk=l.pk).order_by("rang")[:10])
    for n in range(1, maxi):
        for combi in combinations(autres, n):
            if l.montant + sum(x.montant for x in combi) == 0:
                return (l,) + combi
    return None


@transaction.atomic
def relier_nulles(releves, utilisateur=None):
    """Relie entre elles des lignes du relevé de somme nulle (aucune écriture : l'argent est sorti puis revenu)."""
    releves = list(releves)
    if len(releves) < 2 or sum(r.montant for r in releves) != 0:
        raise ValueError("La somme des lignes choisies n'est pas nulle.")
    if any(r.rapprochement_id for r in releves):
        raise ValueError("Une des lignes choisies est déjà pointée.")
    r = Rapprochement.objects.create(journal=releves[0].journal, mode="manuel", cree_par=utilisateur)
    LigneReleve.objects.filter(pk__in=[x.pk for x in releves]).update(rapprochement=r)
    return r


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
        if autre and autre.date == l.date and autre.montant == l.montant:     # même jour, même montant : doublon probable
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
def creer_ecriture(l, compte, anal2, utilisateur=None, forcer=False, libelle=""):
    """Un Mvt à deux lignes (banque / contrepartie), aussitôt relié à la ligne du relevé.
    Le code axe 2 n'est porté que par la contrepartie, et seulement si c'est un compte 6 ou 7.

    Refus si la ligne est déjà reliée (pas de double écriture) ou si une écriture identique existe déjà en compta
    (sauf forcer=True)."""
    l = LigneReleve.objects.select_for_update().select_related("journal__compte").get(pk=l.pk)
    if l.rapprochement_id or l.ouverture:
        raise ValueError("Cette ligne a déjà son écriture.")
    banque = l.journal.compte
    anal2 = anal2 if compte.porte_axe2 else None
    if compte.pk == banque.pk:
        raise ValueError("La contrepartie ne peut pas être le compte de la banque elle-même.")
    if not forcer and deja_en_compta(l):
        raise ValueError("Une écriture de même montant existe déjà à une date proche : reliez-la, ou cochez « nouvelle ».")
    m = abs(l.montant)
    mv = Mouvement.objects.create(numero=Mouvement.prochain_numero(), date=l.date, journal=l.journal,
                                  origine="saisie", cree_par=utilisateur,
                                  commentaire=f"Relevé {l.journal.code} du {l.date:%d/%m/%Y} : {l.operation}")
    lib = (libelle or "").strip()[:200] or libelle_releve(l)       # libellé modifié par l'utilisateur, sinon traduction
    entree = l.montant > 0
    ligne_banque = Ligne.objects.create(mouvement=mv, ordre=1, compte=banque, libelle=lib,
                                        debit=m if entree else ZERO, credit=ZERO if entree else m)
    Ligne.objects.create(mouvement=mv, ordre=2, compte=compte, libelle=lib, anal2=anal2,
                         debit=ZERO if entree else m, credit=m if entree else ZERO)
    pointer(l.journal, [l], [ligne_banque], utilisateur, "saisie")
    Modification.objects.create(auteur=utilisateur.get_username() if utilisateur else "", lot="Banque",
                                action="Écriture depuis le relevé", objet=f"Mvt {mv.numero}",
                                apres=f"{l.journal.code} {l.date:%d/%m/%Y} {l.montant} ; {compte.pk} ; {anal2.pk if anal2 else '—'}")
    return mv


def relier(l, ecriture, utilisateur=None):
    """La ligne du relevé est déjà en compta : on la relie à cette écriture (aucune écriture créée)."""
    return pointer(l.journal, [l], [ecriture], utilisateur, "manuel")


# ---------------------------------------------------------------- mémoire des affectations

BRUIT = re.compile(r"\b[A-Z0-9]{8,}\b|\b\d{2}/\d{2}/\d{4}\b|\b\d{3,}\b")   # références, dates, n° de carte


def cle_libelle(libelle):
    """Libellé rapproché de ses voisins : capitales, sans références ni dates (même règle pour tous les relevés)."""
    return " ".join(BRUIT.sub(" ", (libelle or "").upper()).split())


def memoire_affectations():
    """{libellé normalisé : compte de contrepartie} tiré des écritures de banque déjà passées (la plus récente l'emporte) :
    l'historique déjà en compta sert donc de mémoire dès le premier relevé."""
    from .models import Journal
    tresorerie = set(Journal.objects.exclude(compte__isnull=True).values_list("compte_id", flat=True))
    memo = {}
    lignes = (Ligne.objects.filter(compte_id__in=tresorerie).exclude(mouvement__origine="cloture")
              .select_related("mouvement").prefetch_related("mouvement__lignes__compte").order_by("mouvement__date", "pk"))
    for l in lignes:
        autres = [x for x in l.mouvement.lignes.all() if x.compte_id not in tresorerie]
        if len(autres) == 1:
            for cle in {cle_libelle(l.libelle), cle_libelle(l.mouvement.lignes.all()[0].libelle)}:
                if cle:
                    memo[cle] = autres[0].compte
    return memo


def proposition(l, memo):
    """Compte proposé pour une ligne de relevé, ou None."""
    for texte in (l.traduction, l.operation):
        c = memo.get(cle_libelle(texte))
        if c:
            return c
    return None
