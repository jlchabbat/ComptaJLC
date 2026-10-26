"""Modèles d'écritures et abonnements : un modèle se crée depuis un Mvt ; un abonnement passe le modèle à chaque
échéance (écriture libre, tracée), une seule fois par échéance (date de la dernière écriture générée)."""

import calendar
import datetime as dt

from django.db import transaction

from . import corrections
from .models import ZERO, Abonnement, LigneModele, ModeleEcriture


def depuis_mouvement(m, nom):
    """Modèle reprenant le journal et les lignes (comptes, libellés, montants) d'un Mvt."""
    nom = nom.strip()[:60]
    if not nom:
        raise ValueError("Donner un nom au modèle.")
    if ModeleEcriture.objects.filter(nom=nom).exists():
        raise ValueError(f"Un modèle « {nom} » existe déjà.")
    with transaction.atomic():
        modele = ModeleEcriture.objects.create(nom=nom, journal=m.journal)
        for i, l in enumerate(m.lignes.all()):
            LigneModele.objects.create(modele=modele, ordre=i, compte=l.compte, libelle=l.libelle, debit=l.debit, credit=l.credit)
    return modele


def lignes_initiales(modele):
    """Lignes du formulaire d'écriture libre pré-remplies par le modèle."""
    return [{"compte": l.compte_id, "libelle": l.libelle, "debit": l.debit or None, "credit": l.credit or None}
            for l in modele.lignes.all()]


def _date(annee, mois, jour):
    return dt.date(annee, mois, min(jour, calendar.monthrange(annee, mois)[1]))


def _a_venir(a):
    """Échéances non encore générées, dans l'ordre, jusqu'à la fin de l'abonnement."""
    k = 0
    while True:
        mois = a.debut.month - 1 + k * a.periodicite
        if a.debut.year + mois // 12 > 9998:
            return
        d = _date(a.debut.year + mois // 12, mois % 12 + 1, a.jour)
        if a.fin and d > a.fin:
            return
        if d >= a.debut and (a.derniere is None or d > a.derniere):
            yield d
        k += 1


def echeances(a, jusquau):
    """Dates à générer : après la dernière écriture générée, jusqu'à la date demandée et la fin de l'abonnement."""
    res = []
    for d in _a_venir(a):
        if d > jusquau:
            break
        res.append(d)
    return res


def prochaine(a):
    return next(_a_venir(a), None)


def generer(jusquau, utilisateur):
    """Passe toutes les échéances dues ; renvoie (Mvt créés, erreurs). Un abonnement s'arrête à sa première erreur."""
    crees, erreurs = [], []
    for a in Abonnement.objects.filter(actif=True, modele__actif=True).select_related("modele__journal"):
        lignes = list(a.modele.lignes.select_related("compte"))
        for d in echeances(a, jusquau):
            saisie = [corrections.LigneSaisie(None, l.compte, f"{l.libelle} {d:%m/%Y}"[:200], l.debit, l.credit) for l in lignes]
            try:
                with transaction.atomic():
                    m = corrections.creer(d, a.modele.journal, saisie, f"abonnement {a.modele.nom}, échéance du {d:%d/%m/%Y}",
                                          utilisateur)
                    a.derniere = d
                    a.save(update_fields=["derniere"])
                crees.append(m)
            except ValueError as e:
                erreurs.append(f"{a.modele.nom}, échéance du {d:%d/%m/%Y} : {e}")
                break
    return crees, erreurs


def total(modele):
    return sum((l.debit for l in modele.lignes.all()), ZERO)
