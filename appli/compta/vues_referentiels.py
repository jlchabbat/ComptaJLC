"""Exports des référentiels, un fichier Excel chacun (Éditions › Exports des référentiels).

Les référentiels du classeur Parametres.xlsx (plan comptable, journaux, axes…) s'exportent feuille par feuille, dans le
même format : un fichier exporté se réimporte tel quel (Administration › Paramètres (Excel)). S'y ajoutent les
exercices, les tiers et, pour l'administrateur, les utilisateurs. Une copie est écrite dans le dossier Exports."""

import datetime as dt
import io
import re
import unicodedata

import openpyxl
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import render

from . import dossiers, echanges
from . import parametres as prm
from .models import Modification

echanger = permission_required("compta.echanger_fichiers", raise_exception=True)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def slug(nom):
    return re.sub(r"[^A-Za-z0-9]+", "", unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().title())


def _utilisateurs():
    from .vues_utilisateurs import role
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Utilisateurs"
    ws.append(["Identifiant", "Prénom", "Nom", "E-mail", "Rôle", "Actif", "Dernière connexion"])
    for u in User.objects.prefetch_related("groups").order_by("username"):
        ws.append([u.username, u.first_name, u.last_name, u.email, role(u), "Oui" if u.is_active else "Non",
                   u.last_login.replace(tzinfo=None) if u.last_login else None])
    return wb


def referentiels(user):
    """[(nom de fichier, libellé, description, fabrique du classeur)]"""
    res = [(slug(f.nom), f.nom, f.aide, lambda f=f: prm.classeur([f.nom])) for f in prm.FEUILLES]
    for nom in ("Exercices", "Tiers"):
        f = echanges.PAR_NOM[nom]
        res.append((nom, f.contenu, "Même format que la page Imports / Exports.", lambda f=f: echanges.classeur(f, f.exporter())))
    if user.is_superuser:
        res.append(("Utilisateurs", "Utilisateurs", "Identifiants, rôles, e-mails (sans les mots de passe).", _utilisateurs))
    return res


@login_required
@echanger
def liste(request):
    return render(request, "compta/referentiels.html", {"referentiels": referentiels(request.user)})


@login_required
@echanger
def exporter(request, nom):
    if nom == "Parametres":
        contenu, fichier = prm.contenu_classeur(), "Parametres"
    else:
        trouve = next((r for r in referentiels(request.user) if r[0] == nom), None)
        if not trouve:
            raise (PermissionDenied if nom == "Utilisateurs" else Http404)("Référentiel inconnu.")
        tampon = io.BytesIO()
        trouve[3]().save(tampon)
        contenu, fichier = tampon.getvalue(), nom
    nom_date = f"{fichier}_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"
    (dossiers.exports() / nom_date).write_bytes(contenu)
    Modification.objects.create(auteur=request.user.get_username(), lot="Référentiels", action="Export", objet=nom_date)
    r = HttpResponse(contenu, content_type=XLSX)
    r["Content-Disposition"] = f'attachment; filename="{fichier}.xlsx"'
    return r
