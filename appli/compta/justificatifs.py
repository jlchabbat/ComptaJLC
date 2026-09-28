"""Justificatifs (scans, photos) rattachés aux mouvements.

Fichiers rangés dans <dossier des données>/Justificatifs/<année>/Mvt<n°>_<rang>_<nom>, hors du code : ils survivent
aux mises à jour. Ajouter un justificatif ne change pas la comptabilité ; le supprimer est refusé dans un exercice clos.
Chaque ajout ou suppression est inscrit dans l'historique."""

import mimetypes
import re
import unicodedata

from django.conf import settings

from .models import Exercice, Justificatif, Modification

EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tif", ".tiff")
TAILLE_MAXI = 10 * 1024 * 1024          # 10 Mo par fichier


def dossier():
    d = settings.DATA_DIR / "Justificatifs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def chemin(j):
    return dossier() / j.chemin


def type_mime(j):
    return mimetypes.guess_type(j.nom)[0] or "application/octet-stream"


def _nom_sur(nom):
    nom = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode()
    nom = re.sub(r"[^A-Za-z0-9._-]+", "_", nom).strip("._") or "document"
    return nom[-80:]


def verifier(fichier):
    """Message d'erreur, ou '' si le fichier est accepté."""
    nom = fichier.name or ""
    if not nom.lower().endswith(EXTENSIONS):
        return f"« {nom} » : format non accepté (PDF ou image : JPG, PNG, HEIC…)."
    if fichier.size > TAILLE_MAXI:
        return f"« {nom} » : fichier trop volumineux ({fichier.size // (1024 * 1024)} Mo ; 10 Mo au plus)."
    if fichier.size == 0:
        return f"« {nom} » : fichier vide."
    return ""


def ajouter(mouvement, fichier, description="", auteur=""):
    """Enregistre le fichier (objet UploadedFile ou File) et renvoie le Justificatif. Lève ValueError si refusé."""
    erreur = verifier(fichier)
    if erreur:
        raise ValueError(erreur)
    rang = mouvement.justificatifs.count() + 1
    relatif = f"{mouvement.date:%Y}/Mvt{mouvement.numero}_{rang}_{_nom_sur(fichier.name)}"
    while Justificatif.objects.filter(chemin=relatif).exists() or (dossier() / relatif).exists():
        rang += 1
        relatif = f"{mouvement.date:%Y}/Mvt{mouvement.numero}_{rang}_{_nom_sur(fichier.name)}"
    cible = dossier() / relatif
    cible.parent.mkdir(parents=True, exist_ok=True)
    with open(cible, "wb") as sortie:
        for morceau in fichier.chunks():
            sortie.write(morceau)
    j = Justificatif.objects.create(mouvement=mouvement, chemin=relatif, nom=fichier.name[:150],
                                    description=description[:150], taille=cible.stat().st_size, ajoute_par=auteur)
    Modification.objects.create(auteur=auteur, lot="Justificatifs", action="Ajout d'un justificatif",
                                objet=f"Mvt {mouvement.numero}", apres=f"{j.nom} ({j.taille // 1024} Ko) {description}"[:300])
    return j


def refus_suppression(j):
    if Exercice.date_close(j.mouvement.date):
        return "Mouvement dans un exercice clos : ses justificatifs ne se suppriment plus."
    return ""


def supprimer(j, auteur=""):
    refus = refus_suppression(j)
    if refus:
        raise ValueError(refus)
    fichier = chemin(j)
    Modification.objects.create(auteur=auteur, lot="Justificatifs", action="Suppression d'un justificatif",
                                objet=f"Mvt {j.mouvement.numero}", avant=f"{j.nom} {j.description}"[:300])
    j.delete()
    if fichier.exists():
        fichier.unlink()
