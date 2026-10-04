from datetime import date

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Les montants sont stockés en centimes (entiers) : pas d'erreur d'arrondi.


class Compte(db.Model):
    numero = db.Column(db.String(12), primary_key=True)
    libelle = db.Column(db.String(200), nullable=False)

    @property
    def classe(self):
        return self.numero[:1]


class Journal(db.Model):
    code = db.Column(db.String(8), primary_key=True)
    libelle = db.Column(db.String(100), nullable=False)


class Axe(db.Model):
    """Axe analytique paramétrable (nombre et noms libres)."""
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(60), unique=True, nullable=False)
    codes = db.relationship("CodeAnalytique", backref="axe", order_by="CodeAnalytique.code")


class CodeAnalytique(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    axe_id = db.Column(db.Integer, db.ForeignKey("axe.id"), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    libelle = db.Column(db.String(200), nullable=False)
    __table_args__ = (db.UniqueConstraint("axe_id", "code"),)


class Ecriture(db.Model):
    """Un mouvement = une opération équilibrée (somme débits = somme crédits)."""
    mvt = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    journal_code = db.Column(db.String(8), db.ForeignKey("journal.code"), nullable=False)
    piece = db.Column(db.String(30), default="")
    libelle = db.Column(db.String(200), nullable=False)
    journal = db.relationship("Journal")
    lignes = db.relationship("Ligne", backref="ecriture", cascade="all, delete-orphan")


class Ligne(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mvt = db.Column(db.Integer, db.ForeignKey("ecriture.mvt"), nullable=False)
    compte_numero = db.Column(db.String(12), db.ForeignKey("compte.numero"), nullable=False)
    debit = db.Column(db.Integer, nullable=False, default=0)
    credit = db.Column(db.Integer, nullable=False, default=0)
    compte = db.relationship("Compte")
    analytiques = db.relationship("LigneAnalytique", backref="ligne", cascade="all, delete-orphan")


class LigneAnalytique(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ligne_id = db.Column(db.Integer, db.ForeignKey("ligne.id"), nullable=False)
    code_id = db.Column(db.Integer, db.ForeignKey("code_analytique.id"), nullable=False)
    code = db.relationship("CodeAnalytique")
