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


# ---------------------------------------------------------------- documents existants (dépôt en masse)

echanger = permission_required("compta.echanger_fichiers", raise_exception=True)


@login_required
@echanger
def a_classer(request):
    """Déposer des documents existants (fichiers ou ZIP), vérifier les rattachements proposés, rattacher."""
    auteur = request.user.get_username()
    if request.method == "POST":
        if "ecarter" in request.POST:
            try:
                moteur.ecarter(request.POST["ecarter"])
                messages.info(request, f"« {moteur.nom_affiche(request.POST['ecarter'])} » écarté (fichier supprimé).")
            except ValueError as e:
                messages.error(request, str(e))
        elif "deposer" in request.POST:
            n, refus = 0, []
            for f in request.FILES.getlist("fichiers"):
                if f.size > 200 * 1024 * 1024:
                    refus.append(f"« {f.name} » : plus de 200 Mo ; le découper en plusieurs ZIP.")
                    continue
                deposes, r = moteur.deposer(f.name, f.read())
                n, refus = n + len(deposes), refus + r
            messages.success(request, f"{n} document(s) déposé(s) : vérifiez les rattachements proposés puis cliquez « Rattacher ».")
            for e in refus[:20]:
                messages.error(request, e)
        elif "rattacher" in request.POST:
            faits, erreurs = 0, []
            for i, nom in enumerate(request.POST.getlist("nom")):
                if not request.POST.get(f"garder_{i}"):
                    continue
                numero = request.POST.get(f"mvt_{i}", "").strip()
                m = Mouvement.objects.filter(numero=numero).first() if numero.isdigit() else None
                if not m:
                    erreurs.append(f"« {moteur.nom_affiche(nom)} » : n° de Mvt {numero or 'vide'} inconnu, non rattaché.")
                    continue
                try:
                    moteur.rattacher(nom, m, request.POST.get(f"desc_{i}", "").strip(), auteur)
                    faits += 1
                except ValueError as e:
                    erreurs.append(str(e))
            messages.success(request, f"{faits} document(s) rattaché(s) à leur mouvement.")
            for e in erreurs[:20]:
                messages.error(request, e)
        return redirect("justificatifs_a_classer")
    lignes = moteur.a_classer()
    for l in lignes:
        m = l["mouvement"]
        if m:
            premiere = m.lignes.order_by("ordre").first()
            l["detail"] = f"{m.date:%d/%m/%Y} · {m.journal_id} · pièce {m.piece} · {premiere.libelle if premiere else ''}"
            l["montant"] = m.total_debit
    from django.shortcuts import render
    return render(request, "compta/justificatifs_a_classer.html", {
        "lignes": lignes, "proposes": sum(1 for l in lignes if l["mouvement"]), "surs": sum(1 for l in lignes if l["sur"])})


@login_required
@echanger
def voir_a_classer(request):
    try:
        f = moteur.fichier_a_classer(request.GET.get("nom", ""))
    except ValueError:
        raise Http404
    import mimetypes
    return FileResponse(open(f, "rb"), filename=moteur.nom_affiche(f.name),
                        content_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream")
