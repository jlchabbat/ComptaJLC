"""Sauvegarde, restauration et remise à zéro de la base (trésorier, administrateur).

Toute opération qui remplace les données commence par une sauvegarde datée dans Exports/Sauvegardes."""

import datetime as dt
import sqlite3
from pathlib import Path

from django.core.management import call_command
from django.db import connection

TABLES_COMPTA = ("compta_mouvement", "compta_ligne", "compta_compte")


def dossier():
    from .dossiers import sauvegardes
    return sauvegardes()


def liste():
    return sorted(dossier().glob("*.sqlite3"), key=lambda p: p.stat().st_mtime, reverse=True)


GARDER = 3                                  # sauvegardes de la base conservées (demande du trésorier)


def sauvegarder(motif="manuelle", proteger=None):
    """Copie cohérente de la base (API de sauvegarde SQLite), même pendant que le site tourne.
    proteger : sauvegarde à ne pas effacer en faisant de la place (celle qu'on va restaurer)."""
    connection.ensure_connection()
    base = f"comptajlc_{dt.datetime.now():%Y-%m-%d_%H%M%S}_{motif}"
    chemin, n = dossier() / f"{base}.sqlite3", 1
    while chemin.exists():                  # deux sauvegardes dans la même seconde : pas d'écrasement
        n += 1
        chemin = dossier() / f"{base}_{n}.sqlite3"
    dest = sqlite3.connect(chemin)
    with dest:
        connection.connection.backup(dest)
    dest.close()
    garde = {chemin.resolve()} | ({Path(proteger).resolve()} if proteger else set())
    for vieux in [p for p in liste() if p.resolve() not in garde][GARDER - 1:]:     # garde les 3 dernières
        vieux.unlink()
    return chemin


def verifier(chemin):
    """Refuse un fichier qui n'est pas une base ComptaJLC."""
    try:
        src = sqlite3.connect(f"file:{chemin}?mode=ro", uri=True)
        tables = {r[0] for r in src.execute("select name from sqlite_master where type='table'")}
        n = src.execute("select count(*) from compta_mouvement").fetchone()[0] if "compta_mouvement" in tables else None
        src.close()
    except sqlite3.DatabaseError:
        raise ValueError("Ce fichier n'est pas une base de données SQLite.")
    if not set(TABLES_COMPTA) <= tables:
        raise ValueError("Ce fichier n'est pas une sauvegarde ComptaJLC.")
    return n


def restaurer(chemin):
    """Remplace toute la base par la sauvegarde (comptes utilisateurs compris), puis la met au niveau du code."""
    n = verifier(chemin)
    avant = sauvegarder("avant-restauration", proteger=chemin)
    connection.ensure_connection()
    src = sqlite3.connect(chemin)
    src.backup(connection.connection)
    src.close()
    call_command("migrate", verbosity=0)
    from .saisie import initialiser_parametres
    initialiser_parametres()
    return n, avant


def reprendre_classeur(chemin):
    """Remet la comptabilité à zéro puis reprend le classeur ComptaJLC.xlsm (les comptes utilisateurs sont gardés)."""
    import io
    avant = sauvegarder("avant-reprise")
    sortie = io.StringIO()
    call_command("importer_classeur", str(chemin), remplacer=True, stdout=sortie)
    return sortie.getvalue().strip(), avant
