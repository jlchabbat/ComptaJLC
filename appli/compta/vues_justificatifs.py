"""Justificatifs d'un mouvement : ajouter (plusieurs fichiers ou une photo), consulter, supprimer."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from . import justificatifs as moteur
from .models import Justificatif, Mouvement

consulter = permission_required("compta.view_mouvement", raise_exception=True)


def peut_ajouter(user):
    return user.has_perm("compta.add_mouvement") or user.has_perm("compta.change_mouvement")


@login_required
@require_POST
def ajouter(request, numero):
    if not peut_ajouter(request.user):
        raise PermissionDenied
    m = get_object_or_404(Mouvement, numero=numero)
    fichiers = request.FILES.getlist("fichiers")
    if not fichiers:
        messages.error(request, "Choisissez au moins un fichier (PDF ou photo).")
    description = request.POST.get("description", "").strip()
    ajoutes = []
    for f in fichiers:
        try:
            ajoutes.append(moteur.ajouter(m, f, description, request.user.get_username()))
        except ValueError as e:
            messages.error(request, str(e))
    if ajoutes:
        messages.success(request, f"{len(ajoutes)} justificatif(s) joint(s) au mouvement {m.numero}.")
    return redirect("mouvement", m.numero)


@login_required
@consulter
def voir(request, pk):
    j = get_object_or_404(Justificatif.objects.select_related("mouvement"), pk=pk)
    fichier = moteur.chemin(j)
    if not fichier.exists():
        raise Http404("Fichier introuvable sur le serveur.")
    return FileResponse(open(fichier, "rb"), as_attachment="telecharger" in request.GET, filename=j.nom,
                        content_type=moteur.type_mime(j))


@login_required
@require_POST
def supprimer(request, pk):
    if not request.user.has_perm("compta.change_mouvement"):
        raise PermissionDenied
    j = get_object_or_404(Justificatif.objects.select_related("mouvement"), pk=pk)
    numero = j.mouvement.numero
    try:
        moteur.supprimer(j, request.user.get_username())
        messages.success(request, f"Justificatif « {j.nom} » supprimé (inscrit dans l'historique).")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("mouvement", numero)
