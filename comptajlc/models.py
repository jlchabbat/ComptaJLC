from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Les montants sont stockés en centimes (entiers) : pas d'erreur d'arrondi.


STATUTS = {0: "Non affecté", 1: "En cours", 2: "Terminé"}


class CodeAxe1(db.Model):
    """Axe 1 : rattaché aux comptes du plan comptable (rubrique du compte)."""
    __tablename__ = "code_axe1"
    code = db.Column(db.String(20), primary_key=True)
    libelle = db.Column(db.String(200), nullable=False)
    statut = db.Column(db.Integer, nullable=False, default=1)


class CodeAxe2(db.Model):
    """Axe 2 : activité / projet, indépendant du plan ; choisi à la saisie (comptes 6 et 7)."""
    __tablename__ = "code_axe2"
    code = db.Column(db.String(20), primary_key=True)
    libelle = db.Column(db.String(200), nullable=False)
    statut = db.Column(db.Integer, nullable=False, default=1)


class Compte(db.Model):
    numero = db.Column(db.String(12), primary_key=True)
    libelle = db.Column(db.String(200), nullable=False)
    axe1_code = db.Column(db.String(20), db.ForeignKey("code_axe1.code"))
    lettrable = db.Column(db.Boolean, nullable=False, default=False)
    actif = db.Column(db.Boolean, nullable=False, default=True)
    axe1 = db.relationship("CodeAxe1")

    @property
    def classe(self):
        return self.numero[:1]


class Journal(db.Model):
    code = db.Column(db.String(8), primary_key=True)
    libelle = db.Column(db.String(100), nullable=False)


class Ecriture(db.Model):
    """Un mouvement = une opération équilibrée (somme débits = somme crédits)."""
    mvt = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    journal_code = db.Column(db.String(8), db.ForeignKey("journal.code"), nullable=False)
    piece = db.Column(db.String(30), default="")
    lien = db.Column(db.String(300), default="")  # lien vers le justificatif
    libelle = db.Column(db.String(200), nullable=False)
    journal = db.relationship("Journal")
    lignes = db.relationship("Ligne", backref="ecriture", cascade="all, delete-orphan")


class Ligne(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mvt = db.Column(db.Integer, db.ForeignKey("ecriture.mvt"), nullable=False)
    compte_numero = db.Column(db.String(12), db.ForeignKey("compte.numero"), nullable=False)
    debit = db.Column(db.Integer, nullable=False, default=0)
    credit = db.Column(db.Integer, nullable=False, default=0)
    axe2_code = db.Column(db.String(20), db.ForeignKey("code_axe2.code"))
    compte = db.relationship("Compte")
    axe2 = db.relationship("CodeAxe2")


class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(60), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(256), nullable=False)


class Historique(db.Model):
    """Trace de chaque création, modification et suppression d'écriture (jamais effacée)."""
    id = db.Column(db.Integer, primary_key=True)
    quand = db.Column(db.DateTime, nullable=False, default=datetime.now)
    utilisateur = db.Column(db.String(60), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # création / modification / suppression
    mvt = db.Column(db.Integer, nullable=False)
    motif = db.Column(db.String(300), default="")
    avant = db.Column(db.Text)  # JSON de l'écriture avant (None à la création)
    apres = db.Column(db.Text)  # JSON de l'écriture après (None à la suppression)
