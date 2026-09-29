"""Justificatifs d'un mouvement : ajouter (plusieurs fichiers ou une photo), consulter, supprimer."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST

from . import justificatifs as moteur
from . import reglages
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
    if "a_classer" in request.POST:                       # document déjà déposé (Justificatifs existants)
        noms = request.POST.getlist("a_classer")
        if not noms:
            messages.error(request, "Choisissez au moins un document dans la liste.")
        faits = 0
        for nom in noms:
            try:
                moteur.rattacher(nom, m, request.POST.get("description", "").strip(), request.user.get_username())
                faits += 1
            except ValueError as e:
                messages.error(request, str(e))
        if faits:
            messages.success(request, f"{faits} document(s) déposé(s) rattaché(s) au mouvement {m.numero}.")
        return redirect("mouvement", m.numero)
    if "lien" in request.POST:                            # document resté en ligne (SUMIT…) : on garde son adresse
        hebergeur = reglages.lire("hebergeur_liens")
        nom = f"Document {hebergeur}" if hebergeur and hebergeur.lower() in request.POST["lien"].lower() else ""
        try:
            moteur.ajouter_lien(m, request.POST["lien"], nom,
                                request.POST.get("description", "").strip(), request.user.get_username())
            messages.success(request, f"Lien joint au mouvement {m.numero}.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect("mouvement", m.numero)
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
@xframe_options_sameorigin
def voir(request, pk):
    j = get_object_or_404(Justificatif.objects.select_related("mouvement"), pk=pk)
    if j.lien:                                            # document resté en ligne (SUMIT…)
        return redirect(j.lien)
    fichier = moteur.chemin(j)
    if not fichier.exists():
        raise Http404("Fichier introuvable sur le serveur.")
    return FileResponse(open(fichier, "rb"), as_attachment="telecharger" in request.GET, filename=j.nom,
                        content_type=moteur.type_mime(j))


@login_required
@require_POST
def copier(request, pk):
    """Joindre aussi ce document à d'autres mouvements (« 412 » ou « 412+430 »)."""
    if not peut_ajouter(request.user):
        raise PermissionDenied
    j = get_object_or_404(Justificatif.objects.select_related("mouvement"), pk=pk)
    for n in moteur.numeros(request.POST.get("mvt", "")) or [None]:
        cible = Mouvement.objects.filter(numero=n).first() if n else None
        if not cible:
            messages.error(request, f"Mvt {n or '(vide)'} inconnu : « {j.nom} » n'y est pas joint.")
            continue
        try:
            moteur.copier(j, cible, request.user.get_username())
            messages.success(request, f"« {j.nom} » joint aussi au mouvement {cible.numero}.")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect("mouvement", j.mouvement.numero)


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


def echanger(vue):
    """Dépôt et classement des justificatifs : réservé à ceux qui peuvent joindre un document à un mouvement (trésorier, administrateur)."""
    from functools import wraps

    @wraps(vue)
    def controle(request, *a, **k):
        if not peut_ajouter(request.user):
            raise PermissionDenied
        return vue(request, *a, **k)
    return controle


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
        elif "rapatrier" in request.POST:                 # par paquets : la page ne doit pas attendre trop longtemps
            faits, erreurs, restent = moteur.rapatrier_tous(auteur, limite=25)
            messages.success(request, f"{faits} document(s) copié(s) sur le site ; {restent} encore en ligne.")
            for e in erreurs[:20]:
                messages.error(request, e)
        elif request.POST.get("action_rattaches"):
            return _actions_rattaches(request, auteur)
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
                saisie = request.POST.get(f"mvt_{i}", "").strip()
                nums = moteur.numeros(saisie)                     # « 389 » ou « 389+412 » : plusieurs mouvements
                mvts = [Mouvement.objects.filter(numero=n).first() for n in nums]
                if not nums or not all(mvts):
                    inconnus = ", ".join(str(n) for n, mv in zip(nums, mvts) if not mv) or "vide"
                    erreurs.append(f"« {moteur.nom_affiche(nom)} » : n° de Mvt {inconnus} inconnu, non rattaché.")
                    continue
                try:
                    j = moteur.rattacher(nom, mvts[0], request.POST.get(f"desc_{i}", "").strip(), auteur)
                    faits += 1
                    for autre in mvts[1:]:
                        moteur.copier(j, autre, auteur)
                except ValueError as e:
                    erreurs.append(str(e))
            messages.success(request, f"{faits} document(s) rattaché(s) à leur mouvement.")
            for e in erreurs[:20]:
                messages.error(request, e)
        return redirect("justificatifs_a_classer")
    q = request.GET.get("q", "").strip()
    rattaches = Justificatif.objects.select_related("mouvement").order_by("-mouvement__numero", "id")
    if q:
        nums = moteur.numeros(q)
        rattaches = rattaches.filter(mouvement__numero__in=nums) if q.replace("+", "").replace(" ", "").isdigit() and nums \
            else rattaches.filter(nom__icontains=q)
    nb_rattaches = rattaches.count()
    lignes = moteur.a_classer()
    for l in lignes:
        m = l["mouvement"]
        if m:
            premiere = m.lignes.order_by("ordre").first()
            l["detail"] = f"{m.date:%d/%m/%Y} · {m.journal_id} · pièce {m.piece} · {premiere.libelle if premiere else ''}"
            l["montant"] = m.total_debit
    from django.shortcuts import render
    return render(request, "compta/justificatifs_a_classer.html", {
        "en_ligne": Justificatif.objects.exclude(lien="").count(),
        "rattaches": rattaches[:200], "nb_rattaches": nb_rattaches, "q": q,
        "peut_supprimer": request.user.has_perm("compta.change_mouvement"),
        "lignes": lignes, "proposes": sum(1 for l in lignes if l["mouvement"]), "surs": sum(1 for l in lignes if l["sur"])})


def _actions_rattaches(request, auteur):
    """Désaffecter, supprimer, exporter (ZIP) ou imprimer les documents rattachés cochés."""
    from django.http import HttpResponse
    from django.shortcuts import render
    action = request.POST["action_rattaches"]
    choisis = list(Justificatif.objects.select_related("mouvement").filter(pk__in=request.POST.getlist("doc")))
    if not choisis:
        messages.error(request, "Cochez d'abord au moins un document rattaché.")
        return redirect("justificatifs_a_classer")
    if action == "exporter":
        import datetime
        rep = HttpResponse(moteur.archive_zip(choisis), content_type="application/zip")
        rep["Content-Disposition"] = f'attachment; filename="Justificatifs_{datetime.date.today():%Y-%m-%d}.zip"'
        return rep
    if action == "imprimer":
        return render(request, "compta/justificatifs_imprimer.html", {"documents": choisis})
    if action in ("desaffecter", "supprimer"):
        if action == "supprimer" and not request.user.has_perm("compta.change_mouvement"):
            raise PermissionDenied
        faits = 0
        for j in choisis:
            try:
                (moteur.desaffecter if action == "desaffecter" else moteur.supprimer)(j, auteur)
                faits += 1
            except ValueError as e:
                messages.error(request, f"Mvt {j.mouvement.numero} · {j.nom} : {e}")
        if faits:
            messages.success(request, f"{faits} document(s) détaché(s) : ils sont de nouveau dans « Vérifier et rattacher »."
                             if action == "desaffecter" else f"{faits} document(s) supprimé(s) (inscrit dans l'historique).")
    return redirect("justificatifs_a_classer")


@login_required
@xframe_options_sameorigin
def voir_a_classer(request):
    if not peut_ajouter(request.user):                     # aperçu depuis le mouvement ou la page de classement
        raise PermissionDenied
    nom = request.GET.get("nom", "")
    if nom.startswith("lien:"):
        try:
            return redirect(moteur._lien_en_attente(nom)[0]["lien"])
        except ValueError:
            raise Http404
    try:
        f = moteur.fichier_a_classer(request.GET.get("nom", ""))
    except ValueError:
        raise Http404
    import mimetypes
    return FileResponse(open(f, "rb"), filename=moteur.nom_affiche(f.name),
                        content_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream")
