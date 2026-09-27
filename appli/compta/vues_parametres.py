"""Page « Paramètres (Excel) » : le classeur Parametres.xlsx, modifié dans Excel puis réinjecté.

Deux chemins : le dossier Imports (Imports/Parametres.xlsx, sur le PC où tourne ComptaBB) ou le navigateur
(télécharger, puis envoyer le fichier modifié). Réservé à l'administrateur et au trésorier (droit
« echanger_fichiers ») : pour les autres utilisateurs, l'application ignore les dossiers Imports et Exports."""

import datetime as dt
import shutil

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from . import base_donnees as bd
from . import dossiers
from . import parametres as moteur

echanger = permission_required("compta.echanger_fichiers", raise_exception=True)
TAILLE_MAXI = 5 * 1024 * 1024


class ImportParametresForm(forms.Form):
    fichier = forms.FileField(label="Classeur Parametres.xlsx modifié")

    def clean_fichier(self):
        f = self.cleaned_data["fichier"]
        if not f.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("Un classeur Excel .xlsx est attendu.")
        if f.size > TAILLE_MAXI:
            raise forms.ValidationError("Fichier trop volumineux (5 Mo au plus).")
        return f


def fichier_imports():
    return dossiers.imports() / moteur.NOM_FICHIER


def _importer(request, nom, contenu):
    sauvegarde = bd.sauvegarder("avant_import_parametres")
    try:
        rapport = moteur.importer(contenu, auteur=request.user.get_username())
    except ValueError as e:
        messages.error(request, str(e))
        return None
    if rapport.erreurs:
        messages.error(request, f"Import de {nom} refusé : {len(rapport.erreurs)} ligne(s) à corriger. Rien n'a été enregistré.")
    else:
        messages.success(request, f"Import de {nom} : {rapport.resume}. Sauvegarde préalable : {sauvegarde.name}.")
    return rapport


@login_required
@echanger
def parametres(request):
    form, rapport, chemin = ImportParametresForm(), None, fichier_imports()
    if request.method == "POST":
        if "preparer" in request.POST:
            if chemin.exists():             # la version précédente (peut-être modifiée) est gardée dans Exports
                copie = dossiers.exports() / f"Parametres_{dt.datetime.now():%Y-%m-%d_%H%M%S}_remplace.xlsx"
                shutil.copy2(chemin, copie)
                messages.info(request, f"L'ancien fichier est gardé dans Exports : {copie.name}.")
            try:
                chemin.write_bytes(moteur.contenu_classeur())
            except PermissionError:
                messages.error(request, f"{chemin.name} est ouvert dans Excel : fermez-le puis recommencez.")
            else:
                messages.success(request, f"Paramètres actuels écrits dans Imports/{chemin.name}.")
            return redirect("parametres")
        if "importer_dossier" in request.POST:
            if not chemin.exists():
                messages.error(request, f"Aucun fichier Imports/{chemin.name} : cliquez d'abord sur « Préparer ».")
            else:
                rapport = _importer(request, f"Imports/{chemin.name}", chemin.read_bytes())
        else:
            form = ImportParametresForm(request.POST, request.FILES)
            if form.is_valid():
                f = form.cleaned_data["fichier"]
                rapport = _importer(request, f.name, f.read())
                if rapport and not rapport.erreurs:
                    form = ImportParametresForm()
    modifie = dt.datetime.fromtimestamp(chemin.stat().st_mtime) if chemin.exists() else None
    return render(request, "compta/parametres.html", {
        "form": form, "rapport": rapport, "feuilles": moteur.FEUILLES, "modifie": modifie})


@login_required
@echanger
def telecharger(request):
    contenu = moteur.contenu_classeur()
    (dossiers.exports() / moteur.NOM_FICHIER).write_bytes(contenu)          # copie de ce qui a été exporté
    return HttpResponse(contenu, headers={
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": f'attachment; filename="{moteur.NOM_FICHIER}"'})
