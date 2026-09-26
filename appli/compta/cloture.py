"""Clôture d'un exercice : contrôles, à-nouveaux (journal AN), affectation du résultat, archive figée.

Les écritures existantes ne sont jamais modifiées : la clôture ajoute un seul mouvement
d'à-nouveaux daté du premier jour de l'exercice suivant et verrouille l'exercice clos."""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import controles as ctrl
from . import etats
from .models import ZERO, Compte, Exercice, Journal, Ligne, Modification, Mouvement, Reglage


@dataclass
class Preparation:
    exercice: Exercice
    suivant: Exercice | None = None
    journal: Journal | None = None
    compte_report: Compte | None = None
    lignes: list = field(default_factory=list)      # (compte, débit, crédit)
    resultat: Decimal = ZERO
    bloquants: list = field(default_factory=list)
    avertissements: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.bloquants


def journal_an():
    code = Reglage.lire("journal_a_nouveaux")
    return Journal.objects.filter(code=code).first() if code else Journal.objects.filter(type="AN").first()


def preparer(ex):
    p = Preparation(exercice=ex, journal=journal_an())
    p.compte_report = Compte.objects.filter(numero=Reglage.lire("compte_report_a_nouveau", "110000")).first()
    if ex.clos:
        p.bloquants.append("Cet exercice est déjà clos.")
    if Exercice.objects.filter(debut__lt=ex.debut, clos=False).exists():
        p.bloquants.append("Un exercice antérieur n'est pas clos : le clôturer d'abord.")
    if not p.journal:
        p.bloquants.append("Aucun journal d'à-nouveaux (type AN, ou réglage journal_a_nouveaux).")
    if not p.compte_report:
        p.bloquants.append("Compte de report à nouveau introuvable (réglage compte_report_a_nouveau).")
    desequilibres = [m for m in Mouvement.objects.filter(date__range=(ex.debut, ex.fin)).prefetch_related("lignes")
                     if m.total_debit != m.total_credit]
    if desequilibres:
        p.bloquants.append(f"{len(desequilibres)} mouvement(s) déséquilibré(s) dans l'exercice (RG-01).")
    b = etats.bilan(ex.fin, ex.debut)
    if not b["equilibre"]:
        p.bloquants.append(f"Bilan déséquilibré avant clôture : actif {etats.montant(b['total_actif'])} ≠ passif {etats.montant(b['total_passif'])}.")
    etat, _ = ctrl.etat_general()
    if etat != "OK":
        p.avertissements.append(f"Contrôles : {etat} (page Contrôles).")
    from .models import LigneFiche, TiersProvisoire
    n = LigneFiche.objects.filter(mouvement__isnull=True, date__range=(ex.debut, ex.fin)).count()
    if n:
        p.avertissements.append(f"{n} ligne(s) de fiches bénévoles de l'exercice non reportée(s).")
    if TiersProvisoire.objects.filter(compte__isnull=True).exists():
        p.avertissements.append("Des tiers provisoires attendent un compte.")
    if b["resultats_anterieurs"]:
        p.avertissements.append(f"Résultats d'exercices antérieurs jamais reportés : {etats.montant(b['resultats_anterieurs'])} ; "
                                "ils sont affectés avec celui de l'exercice.")
    # à-nouveaux : soldes des classes 1 à 5 à la fin de l'exercice, résultat (6 et 7 non reportés) au compte de report
    soldes = etats.soldes_par_compte(etats.lignes_cumulees(ex.fin))
    report = p.compte_report.numero if p.compte_report else None
    p.resultat = -sum((s for k, (_, s) in soldes.items() if k[0] in "67"), ZERO)
    for numero, (_, s) in soldes.items():
        if numero[0] in etats.CLASSES_BILAN:
            if numero == report:
                s -= p.resultat
            if s:
                p.lignes.append((numero, s if s > 0 else ZERO, -s if s < 0 else ZERO))
    if report and report not in soldes and p.resultat:
        p.lignes.append((report, -p.resultat if p.resultat < 0 else ZERO, p.resultat if p.resultat > 0 else ZERO))
    p.lignes.sort()
    p.suivant = Exercice.objects.filter(debut=ex.fin + dt.timedelta(days=1)).first()
    if sum(d for _, d, _ in p.lignes) != sum(c for _, _, c in p.lignes):
        p.bloquants.append("À-nouveaux déséquilibrés.")
    return p


@transaction.atomic
def cloturer(ex, utilisateur, anal2):
    p = preparer(ex)
    if not p.ok:
        raise ValueError(" ".join(p.bloquants))
    suivant = p.suivant
    if not suivant:
        debut = ex.fin + dt.timedelta(days=1)
        try:
            fin = debut.replace(year=debut.year + 1) - dt.timedelta(days=1)
        except ValueError:                     # 29 février
            fin = debut.replace(year=debut.year + 1, day=28) - dt.timedelta(days=1)
        suivant = Exercice.objects.create(libelle=f"Exercice {debut.year}" if debut.month == 1 and debut.day == 1
                                          else f"Exercice {debut:%d/%m/%Y} – {fin:%d/%m/%Y}", debut=debut, fin=fin)
    mv = None
    if p.lignes:
        mv = Mouvement.objects.create(numero=Mouvement.prochain_numero(), date=suivant.debut, journal=p.journal,
                                      piece=Mouvement.prochaine_piece(), origine="cloture", cree_par=utilisateur,
                                      commentaire=f"À-nouveaux de la clôture de « {ex.libelle} »")
        Ligne.objects.bulk_create([Ligne(mouvement=mv, ordre=i, compte_id=n, libelle=f"A NOUVEAU {ex.libelle}".upper()[:200],
                                         debit=d, credit=c, anal2=anal2) for i, (n, d, c) in enumerate(p.lignes)])
    ex.clos, ex.mouvement_an, ex.resultat = True, mv, p.resultat
    ex.cloture_le, ex.cloture_par = timezone.now(), utilisateur.get_username()
    ex.save()
    apres = etats.bilan(suivant.debut, suivant.debut)
    if not apres["equilibre"]:
        raise ValueError("Bilan d'ouverture déséquilibré après les à-nouveaux : clôture annulée.")
    ex.archive = archiver(ex)
    ex.save(update_fields=["archive"])
    Modification.objects.create(auteur=utilisateur.get_username(), lot="Clôture", action="Clôture", objet=ex.libelle,
                                apres=f"résultat {etats.montant(p.resultat)} ; à-nouveaux {mv or 'aucun'} ; archive {ex.archive}")
    return ex


def dossier_archives():
    d = settings.DATA_DIR / "archives"
    d.mkdir(parents=True, exist_ok=True)
    return d


def archiver(ex):
    """Classeur figé en valeurs : états, balance, grand livre et écritures de l'exercice."""
    from .export import classeur_exercice
    nom = f"ComptaBB_{ex.libelle}".replace("/", "-").replace(" ", "_").replace("–", "-")[:80] + ".xlsx"
    classeur_exercice(ex).save(dossier_archives() / nom)
    return nom


def exercices_a_cloturer():
    return Exercice.objects.filter(clos=False).order_by("debut")


def premier_non_clos():
    return exercices_a_cloturer().first()
