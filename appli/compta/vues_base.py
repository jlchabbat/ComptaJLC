"""Page « Base de données » : sauvegarder, télécharger, restaurer, remettre à zéro et reprendre un classeur."""

import tempfile
from pathlib import Path

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from . import base_donnees as bd
from .models import Ligne, Modification, Mouvement

CONFIRMATION = "REMPLACER"


def administrateur(u):
    if not u.is_superuser:
        raise PermissionDenied
    return True


class RemplacementForm(forms.Form):
    fichier = forms.FileField(required=False, label="Fichier (.sqlite3 ou ComptaBB.xlsm)")
    sauvegarde = forms.ChoiceField(required=False, label="…ou une sauvegarde du site")
    confirmation = forms.CharField(label=f"Tapez {CONFIRMATION} pour confirmer")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["sauvegarde"].choices = [("", "—")] + [(p.name, p.name) for p in bd.liste()]

    def clean(self):
        c = super().clean()
        if (c.get("confirmation") or "").strip().upper() != CONFIRMATION:
            self.add_error("confirmation", f"Tapez exactement {CONFIRMATION}.")
        if bool(c.get("fichier")) == bool(c.get("sauvegarde")):
            raise forms.ValidationError("Choisir soit un fichier, soit une sauvegarde du site.")
        return c


def journaliser(request, action, objet, apres=""):
    Modification.objects.create(auteur=request.user.get_username(), lot="Base de données", action=action, objet=objet[:200],
                                apres=apres[:300])


@login_required
@user_passes_test(administrateur)
def base(request):
    form = RemplacementForm(request.POST or None, request.FILES or None) if "remplacer" in request.POST else RemplacementForm()
    if request.method == "POST":
        if "sauvegarder" in request.POST:
            p = bd.sauvegarder()
            journaliser(request, "Sauvegarde", p.name)
            messages.success(request, f"Sauvegarde créée : {p.name}.")
            return redirect("base")
        if "remplacer" in request.POST and form.is_valid():
            c = form.cleaned_data
            auteur = request.user.get_username()
            try:
                if c["sauvegarde"]:
                    chemin = next((p for p in bd.liste() if p.name == c["sauvegarde"]), None)
                    if not chemin:
                        raise ValueError("Sauvegarde introuvable.")
                    nom = chemin.name
                else:
                    f = c["fichier"]
                    nom = f.name
                    suffixe = Path(nom).suffix.lower()
                    if suffixe not in (".sqlite3", ".sqlite", ".db", ".xlsm", ".xlsx"):
                        raise ValueError("Fichier .sqlite3 (sauvegarde) ou .xlsm (classeur ComptaBB) attendu.")
                    tmp = Path(tempfile.mkdtemp()) / f"import{suffixe}"
                    with open(tmp, "wb") as sortie:
                        for morceau in f.chunks():
                            sortie.write(morceau)
                    chemin = tmp
                if chemin.suffix.lower() in (".xlsm", ".xlsx"):
                    resume, avant = bd.reprendre_classeur(chemin)
                    Modification.objects.create(auteur=auteur, lot="Base de données", action="Remise à zéro et reprise",
                                                objet=nom[:200], apres=f"{resume} ; sauvegarde {avant.name}"[:300])
                    messages.success(request, f"Base remise à zéro et reprise depuis {nom} : {resume}. Sauvegarde d'avant : {avant.name}.")
                else:
                    n, avant = bd.restaurer(chemin)
                    Modification.objects.create(auteur=auteur, lot="Base de données", action="Restauration", objet=nom[:200],
                                                apres=f"{n} mouvements ; sauvegarde d'avant {avant.name}"[:300])
                    messages.success(request, f"Base restaurée depuis {nom} ({n} mouvements). Sauvegarde d'avant : {avant.name}.")
            except ValueError as e:
                messages.error(request, f"Rien n'a été remplacé : {e}")
            except Exception as e:                       # reprise refusée par ses contrôles, fichier illisible…
                messages.error(request, f"Échec : {e}. Si les données semblent incomplètes, restaurez la sauvegarde d'avant.")
            return redirect("base")
    return render(request, "compta/base_donnees.html", {
        "form": form, "sauvegardes": [(p.name, p.stat().st_size // 1024) for p in bd.liste()],
        "archives": [(p.name, p.stat().st_size // 1024) for p in archives()],
        "mouvements": Mouvement.objects.count(), "lignes": Ligne.objects.count(), "confirmation": CONFIRMATION})


@login_required
@user_passes_test(administrateur)
def telecharger(request, nom=None):
    if nom is None:
        chemin = bd.sauvegarder("telechargement")
    else:
        chemin = next((p for p in bd.liste() if p.name == nom), None)
        if not chemin:
            raise Http404
    journaliser(request, "Téléchargement de la base", chemin.name)
    return FileResponse(open(chemin, "rb"), as_attachment=True, filename=chemin.name)


def archives():
    from .dossiers import archives as dossier
    return sorted(dossier().glob("*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)


@login_required
@user_passes_test(administrateur)
def telecharger_archive(request, nom):
    chemin = next((p for p in archives() if p.name == nom), None)
    if not chemin:
        raise Http404
    return FileResponse(open(chemin, "rb"), as_attachment=True, filename=chemin.name)
