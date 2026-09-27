"""Emplacement des fichiers échangés : dossiers Imports et Exports (réglages IMPORTS_DIR et EXPORTS_DIR).

Exports/Sauvegardes : copies de la base ; Exports/Archives : classeurs de clôture et historiques effacés ;
Exports/Parametres.xlsx : paramètres exportés. Les fichiers des anciens emplacements (data/sauvegardes,
data/archives) y sont déplacés au premier accès."""

import shutil

from django.conf import settings


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


def imports():
    return _dossier(settings.IMPORTS_DIR)


def exports():
    return _dossier(settings.EXPORTS_DIR)


def sauvegardes():
    return _dossier(settings.EXPORTS_DIR / "Sauvegardes", settings.DATA_DIR / "sauvegardes")


def archives():
    return _dossier(settings.EXPORTS_DIR / "Archives", settings.DATA_DIR / "archives")
