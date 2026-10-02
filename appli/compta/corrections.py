"""Corrections d'écritures par le trésorier (RG-05) : modification d'un mouvement
(rappelé par son numéro), écriture libre. Tout est contrôlé (RG-01 à RG-04) et tracé (commentaire du mouvement et journal)."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import ZERO, CodeAnalytique, Compte, Exercice, Ligne, Modification, Mouvement


@dataclass
class LigneSaisie:
    id: int | None
    compte: Compte
    libelle: str
    debit: Decimal
    credit: Decimal
    anal2: CodeAnalytique | None = None


def verrou(m):
    """Raison pour laquelle le mouvement ne peut pas être modifié, ou ''."""
    if m.origine == "cloture":
        return "À-nouveaux de clôture : ne se modifient pas."
    if Exercice.date_close(m.date):
        return "Mouvement dans un exercice clos (RG-04)."
    return ""


def controler(date, journal, lignes):
    e = []
    if not date:
        e.append("Saisir la date.")
    elif Exercice.date_close(date):
        e.append("Date dans un exercice clos (RG-04).")
    if not journal:
        e.append("Choisir le journal.")
    if len(lignes) < 2:
        e.append("Au moins deux lignes.")
    for i, l in enumerate(lignes, 1):
        if (l.debit > 0) == (l.credit > 0):
            e.append(f"Ligne {i} : un débit OU un crédit (RG-03).")
        if not l.libelle.strip():
            e.append(f"Ligne {i} : libellé manquant.")
    d, c = sum((l.debit for l in lignes), ZERO), sum((l.credit for l in lignes), ZERO)
    if d != c:
        e.append(f"Mouvement déséquilibré : débit {d} ≠ crédit {c} (RG-01).")
    return e


def resume(lignes):
    return " | ".join(f"{l.compte.numero} {'D' if l.debit else 'C'} {l.debit or l.credit} {l.anal2_id or '—'}" for l in lignes)[:300]


def trace(m, texte, utilisateur):
    m.commentaire = (m.commentaire + "\n" if m.commentaire else "") + \
        f"{timezone.localtime():%d/%m/%Y} {utilisateur.get_username()} : {texte}"


def _liberer(ligne):
    """Une ligne qui change de compte ou de montant sort de son rapprochement et de son lettrage."""
    from .releves import depointer
    if ligne.rapprochement_id:
        depointer(ligne.rapprochement)
    if ligne.lettrage:
        Ligne.objects.filter(compte_id=ligne.compte_id, lettrage=ligne.lettrage).update(lettrage="")


@transaction.atomic
def modifier(m, date, journal, lignes, motif, utilisateur):
    if verrou(m):
        raise ValueError(verrou(m))
    motif = motif.strip() or "correction"                 # facultatif : avant / après restent dans l'historique
    erreurs = controler(date, journal, lignes)
    if erreurs:
        raise ValueError(" ".join(erreurs))
    avant = f"{m.date:%d/%m/%Y} {m.journal_id} · " + resume(m.lignes.all())
    existantes = {l.pk: l for l in m.lignes.all()}
    gardees = set()
    for ordre, s in enumerate(lignes):
        l = existantes.get(s.id)
        if l:
            gardees.add(l.pk)
            if (l.compte_id, l.debit, l.credit) != (s.compte.numero, s.debit, s.credit):
                _liberer(l)
                l.refresh_from_db()
            l.ordre, l.compte, l.libelle, l.debit, l.credit = ordre, s.compte, s.libelle.strip(), s.debit, s.credit
            l.anal2 = s.anal2
            l.save()
        else:
            Ligne.objects.create(mouvement=m, ordre=ordre, compte=s.compte, libelle=s.libelle.strip(), debit=s.debit,
                                 credit=s.credit, anal2=s.anal2)
    for pk, l in existantes.items():
        if pk not in gardees:
            _liberer(l)
            Ligne.objects.filter(pk=pk).delete()
    m.date, m.journal = date, journal
    trace(m, f"modifié – {motif.strip()}", utilisateur)
    m.save()
    Modification.objects.create(auteur=utilisateur.get_username(), lot="Corrections", action="Modification",
                                objet=f"Mvt {m.numero} – {motif.strip()}"[:200], avant=avant[:300],
                                apres=(f"{m.date:%d/%m/%Y} {m.journal_id} · " + resume(m.lignes.all()))[:300])
    return m


@transaction.atomic
def creer(date, journal, lignes, motif, utilisateur):
    """Écriture libre (opération diverse, correction)."""
    motif = motif.strip() or "écriture libre"
    erreurs = controler(date, journal, lignes)
    if erreurs:
        raise ValueError(" ".join(erreurs))
    m = Mouvement.objects.create(numero=Mouvement.prochain_numero(), date=date, journal=journal,
                                 origine="correction", cree_par=utilisateur)
    for ordre, s in enumerate(lignes):
        Ligne.objects.create(mouvement=m, ordre=ordre, compte=s.compte, libelle=s.libelle.strip(), debit=s.debit, credit=s.credit,
                             anal2=s.anal2)
    trace(m, f"écriture libre – {motif.strip()}", utilisateur)
    m.save(update_fields=["commentaire"])
    Modification.objects.create(auteur=utilisateur.get_username(), lot="Corrections", action="Écriture libre",
                                objet=f"Mvt {m.numero} – {motif.strip()}"[:200], apres=resume(m.lignes.all()))
    return m


def refus_suppression(m):
    """Raison pour laquelle le mouvement ne peut pas être supprimé, ou ''."""
    if verrou(m):
        return verrou(m)
    if Exercice.objects.filter(mouvement_an=m).exists():
        return "À-nouveaux d'un exercice : ne se suppriment pas."
    return ""


@transaction.atomic
def supprimer(m, utilisateur):
    """Supprime le mouvement (trésorier) : ses lignes sortent des pointages et lettrages, ses justificatifs sont effacés,
    une ligne de fiche bénévole reportée redevient à reporter. L'avant reste dans l'historique."""
    from . import justificatifs
    from .models import LigneFiche
    refus = refus_suppression(m)
    if refus:
        raise ValueError(refus)
    avant = f"{m.date:%d/%m/%Y} {m.journal_id} · " + resume(m.lignes.select_related("compte", "anal2"))
    for l in m.lignes.all():
        _liberer(l)
    fichiers = [justificatifs.chemin(j) for j in m.justificatifs.all()]
    from .models import Fiche
    fiches = list(Fiche.objects.filter(lignes__mouvement=m, statut="reportee").distinct())
    LigneFiche.objects.filter(mouvement=m).update(mouvement=None)
    for f in fiches:                                      # la ligne est à reporter de nouveau
        f.statut = "transmise"
        f.save(update_fields=["statut"])
    numero = m.numero
    m.delete()
    for f in fichiers:
        if f and f.exists():
            f.unlink()
    Modification.objects.create(auteur=utilisateur.get_username(), lot="Corrections", action="Suppression",
                                objet=f"Mvt {numero}", avant=avant[:300],
                                apres=f"{len(fichiers)} justificatif(s) effacé(s)" if fichiers else "")
    return numero
