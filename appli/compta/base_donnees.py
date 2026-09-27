"""Sauvegarde, restauration et remise à zéro de la base (trésorier, administrateur).

Toute opération qui remplace les données commence par une sauvegarde datée dans Exports/Sauvegardes."""

import datetime as dt
import sqlite3

from django.core.management import call_command
from django.db import connection

TABLES_COMPTA = ("compta_mouvement", "compta_ligne", "compta_compte")


def dossier():
    from .dossiers import sauvegardes
    return sauvegardes()


def liste():
    return sorted(dossier().glob("*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)


def sauvegarder(motif="manuelle"):
    """Copie cohérente de la base (API de sauvegarde SQLite), même pendant que le site tourne."""
    connection.ensure_connection()
    chemin = dossier() / f"comptabb_{dt.datetime.now():%Y-%m-%d_%H%M%S}_{motif}.sqlite3"
    dest = sqlite3.connect(chemin)
    with dest:
        connection.connection.backup(dest)
    dest.close()
    for vieux in liste()[30:]:              # garde les 30 dernières
        vieux.unlink()
    return chemin


def verifier(chemin):
    """Refuse un fichier qui n'est pas une base ComptaBB."""
    try:
        src = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
        tables = {r[0] for r in src.execute("select name from sqlite_master where type='table'")}
        n = src.execute("select count(*) from compta_mouvement").fetchone()[0] if "compta_mouvement" in tables else None
        src.close()
    except sqlite3.DatabaseError:
        raise ValueError("Ce fichier n'est pas une base de données SQLite.")
    if not set(TABLES_COMPTA) <= tables:
        raise ValueError("Ce fichier n'est pas une sauvegarde ComptaBB.")
    return n


def restaurer(chemin):
    """Remplace toute la base par la sauvegarde (comptes utilisateurs compris), puis la met au niveau du code."""
    n = verifier(chemin)
    avant = sauvegarder("avant-restauration")
    connection.ensure_connection()
    src = sqlite3.connect(chemin)
    src.backup(connection.connection)
    src.close()
    call_command("migrate", verbosity=0)
    from .saisie import initialiser_parametres
    initialiser_parametres()
    return n, avant


def reprendre_classeur(chemin):
    """Remet la comptabilité à zéro puis reprend le classeur ComptaBB.xlsm (les comptes utilisateurs sont gardés)."""
    import io
    avant = sauvegarder("avant-reprise")
    sortie = io.StringIO()
    call_command("importer_classeur", str(chemin), remplacer=True, stdout=sortie)
    return sortie.getvalue().strip(), avant
