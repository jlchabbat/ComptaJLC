"""Emplacement des fichiers échangés : dossiers Imports, Exports et Sauvegardes.

Chacun se paramètre (Administration › Imports / Exports, ou Reglages.xlsx) par les réglages dossier_imports,
dossier_exports et dossier_sauvegardes ; vide = valeur par défaut (IMPORTS_DIR, EXPORTS_DIR, Exports/Sauvegardes).
Un chemin Windows (D:\\…), hérité de l'ancien programme du PC, est ignoré (dossier par défaut).

Exports/Archives : classeurs de clôture et historiques effacés ; Exports/Parametres.xlsx : paramètres exportés.
Les fichiers des anciens emplacements (data/sauvegardes, data/archives) sont déplacés au premier accès."""

import os
import re
import shutil
from pathlib import Path

from django.conf import settings

REGLAGES = {
    "dossier_imports": "Dossier des fichiers à importer (référentiels, écritures, relevés)",
    "dossier_exports": "Dossier où l'application écrit ses exports",
    "dossier_sauvegardes": "Dossier des sauvegardes de la base (copies .sqlite3)",
}
WINDOWS = re.compile(r"^([A-Za-z]:|\\\\)")


def valable(chemin):
    """Un chemin Windows n'est utilisable que sous Windows (PC) ; un chemin relatif n'est jamais accepté."""
    chemin = (chemin or "").strip().strip('"')
    if not chemin:
        return False
    if os.name == "nt":
        return bool(WINDOWS.match(chemin)) or Path(chemin).is_absolute()
    return not WINDOWS.match(chemin) and Path(chemin).is_absolute()


def reglage(cle):
    from .models import Reglage
    try:
        v = Reglage.lire(cle).strip().strip('"')
    except Exception:                                   # base pas encore créée
        return None
    return Path(v) if valable(v) else None


def _dossier(chemin, ancien=None):
    chemin.mkdir(parents=True, exist_ok=True)
    if ancien is not None and ancien.is_dir() and ancien.resolve() != chemin.resolve():
        for f in ancien.iterdir():
            if f.is_file() and not (chemin / f.name).exists():
                shutil.move(str(f), chemin / f.name)
        try:
            ancien.rmdir()
        except OSError:
            pass
    return chemin


def defaut(cle):
    return {"dossier_imports": Path(settings.IMPORTS_DIR), "dossier_exports": Path(settings.EXPORTS_DIR),
            "dossier_sauvegardes": (reglage("dossier_exports") or Path(settings.EXPORTS_DIR)) / "Sauvegardes"}[cle]


def chemin(cle):
    return reglage(cle) or defaut(cle)


def imports():
    return _dossier(chemin("dossier_imports"))


def exports():
    return _dossier(chemin("dossier_exports"))


def sauvegardes():
    return _dossier(chemin("dossier_sauvegardes"), settings.DATA_DIR / "sauvegardes")


def archives():
    return _dossier(exports() / "Archives", settings.DATA_DIR / "archives")


def copier_export(nom, contenu):
    """Copie dans le dossier Exports d'un fichier téléchargé par le navigateur (tous les exports y aboutissent) ;
    ignorée si le dossier est inaccessible ou le fichier ouvert dans Excel."""
    try:
        (exports() / nom).write_bytes(contenu)
    except OSError:
        pass
