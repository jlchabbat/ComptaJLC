"""Données de départ, modifiables ensuite depuis l'application."""
from .models import Axe, Compte, Journal, db

COMPTES = [
    ("101", "Capital / fonds associatifs"), ("512", "Banque"), ("530", "Caisse"),
    ("401", "Fournisseurs"), ("411", "Clients / membres"),
    ("470", "Compte d'attente"), ("580", "Virements internes"),
    ("606", "Achats non stockés"), ("613", "Locations"), ("625", "Déplacements, réceptions"),
    ("706", "Prestations de services"), ("707", "Ventes"), ("756", "Cotisations"),
]
JOURNAUX = [("AC", "Achats"), ("VT", "Ventes"), ("BQ", "Banque"), ("CA", "Caisse"), ("OD", "Opérations diverses")]


def semer():
    if Compte.query.first() is None:
        db.session.add_all(Compte(numero=n, libelle=l) for n, l in COMPTES)
    if Journal.query.first() is None:
        db.session.add_all(Journal(code=c, libelle=l) for c, l in JOURNAUX)
    if Axe.query.first() is None:
        db.session.add(Axe(nom="Axe 1"))
    db.session.commit()
