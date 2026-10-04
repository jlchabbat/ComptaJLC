"""Données de départ et migration de la base existante."""
from sqlalchemy import inspect, text

from .models import Journal, db

JOURNAUX = [("AC", "Achats"), ("VT", "Ventes"), ("BQ", "Banque"), ("CA", "Caisse"), ("OD", "Opérations diverses")]

# Colonnes ajoutées après la première version (SQLite : ADD COLUMN).
AJOUTS = {
    "compte": [("axe1_code", "VARCHAR(20)"), ("lettrable", "BOOLEAN NOT NULL DEFAULT 0"),
               ("actif", "BOOLEAN NOT NULL DEFAULT 1")],
    "ligne": [("axe2_code", "VARCHAR(20)")],
    "utilisateur": [("role", "VARCHAR(12) NOT NULL DEFAULT 'admin'")],  # comptes existants : administrateurs
    "ecriture": [("lien", "VARCHAR(300) DEFAULT ''")],
}
ANCIENS_AXES = ["ligne_analytique", "code_analytique", "axe"]  # modèle d'axes libres, abandonné


def migrer():
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    for table, colonnes in AJOUTS.items():
        existantes = {c["name"] for c in insp.get_columns(table)}
        for nom, ddl in colonnes:
            if nom not in existantes:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {nom} {ddl}"))
    # Ancien modèle d'axes : supprimé seulement s'il ne porte aucune ventilation.
    if "ligne_analytique" in tables:
        if db.session.execute(text("SELECT COUNT(*) FROM ligne_analytique")).scalar() == 0:
            for t in ANCIENS_AXES:
                db.session.execute(text(f"DROP TABLE IF EXISTS {t}"))
    db.session.commit()


def semer():
    migrer()
    if Journal.query.first() is None:
        db.session.add_all(Journal(code=c, libelle=l) for c, l in JOURNAUX)
    db.session.commit()
