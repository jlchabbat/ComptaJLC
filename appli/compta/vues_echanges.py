"""Page Imports / Exports : fichiers .xlsx du dossier Imports à importer, exports vers le dossier Exports."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from . import dossiers
from . import echanges as moteur
from .models import Reglage

tresorier = permission_required("compta.parametrer", raise_exception=True)      # référentiels compris : administrateur


@login_required
@tresorier
def echanges(request):
    auteur = request.user.get_username()
    if request.method == "POST":
        try:
            if "dossier_pc" in request.POST:                      # dossier habituel sur l'ordinateur de l'utilisateur (simple rappel affiché)
                nouveau = request.POST["dossier_pc"].strip()[:200]
                avant = Reglage.lire("dossier_pc")
                if nouveau != avant:
                    Reglage.objects.update_or_create(cle="dossier_pc", defaults={"valeur": nouveau, "description": "Dossier habituel des fichiers sur le PC"})
                    moteur.Modification.objects.create(auteur=auteur, lot="Échanges", action="Paramètre", objet="dossier_pc", avant=avant, apres=nouveau)
                messages.success(request, "Dossier habituel enregistré.")
            elif "dossiers" in request.POST:
                moteur.changer_dossiers({c: request.POST.get(c, "") for c in moteur.REGLAGES_DOSSIERS}, auteur)
                messages.success(request, f"Dossiers enregistrés : Imports = {moteur.imports()} ; Exports = {moteur.exports()}.")
            elif "deposer" in request.POST:
                envoyes = request.FILES.getlist("fichiers")
                if not envoyes:
                    raise moteur.Refus(["Choisir au moins un fichier à déposer."])
                noms = [n for f in envoyes for n in moteur.deposer(f.name, f.read(), auteur)]
                messages.success(request, f"Déposé(s) dans Imports : {', '.join(noms)}.")
            elif "importer_fichiers" in request.POST:             # procédure simple : déposer puis tout importer en une fois
                envoyes = request.FILES.getlist("fichiers")
                if not envoyes:
                    raise moteur.Refus(["Choisir au moins un fichier à importer."])
                noms = [n for f in envoyes for n in moteur.deposer(f.name, f.read(), auteur)]
                try:
                    comptes_rendus, ignores = moteur.importer_tout(request.user)
                except moteur.Refus:
                    for n in noms:                                # refus : rien n'est gardé, le dossier reste propre
                        try:
                            moteur.retirer(n, auteur)
                        except (KeyError, ValueError, OSError):
                            pass
                    raise
                messages.success(request, f"Import terminé : {len(comptes_rendus)} fichier(s).")
                for x in comptes_rendus:
                    messages.info(request, x)
                if ignores:
                    messages.warning(request, "Non importé(s), structure non reconnue : " + ", ".join(ignores) + ".")
            elif "reinjecter" in request.POST:
                if request.POST.get("confirmation", "").strip().upper() != "REMPLACER":
                    raise moteur.Refus(["Taper REMPLACER pour confirmer la réinjection."])
                comptes_rendus, sauvegarde = moteur.reinjecter(request.user)
                messages.success(request, f"Réinjection terminée (sauvegarde préalable : {sauvegarde.name}).")
                for x in comptes_rendus:
                    messages.info(request, x)
            elif "retirer" in request.POST:
                moteur.retirer(request.POST["retirer"], auteur)
                messages.success(request, f"« {request.POST['retirer']} » supprimé du dossier Imports.")
            elif "tout_importer" in request.POST:
                comptes_rendus, ignores = moteur.importer_tout(request.user)
                messages.success(request, f"Tout importé ({len(comptes_rendus)} fichier(s)) ; les fichiers sont rangés dans "
                                          f"Imports\\{moteur.IMPORTES}.")
                for x in comptes_rendus:
                    messages.info(request, x)
                if ignores:
                    messages.warning(request, "Non importé(s), structure non reconnue : " + ", ".join(ignores) + ".")
            elif "importer" in request.POST:
                f, texte = moteur.importer(request.POST["importer"], request.user)
                messages.success(request, f"{request.POST['importer']} importé ({f.contenu}) : {texte}. "
                                          f"Le fichier est rangé dans Imports\\{moteur.IMPORTES}.")
            elif "tout_sauvegarder" in request.POST:
                ecrits, sauvegarde = moteur.tout_exporter(auteur)
                messages.success(request, f"{len(ecrits)} fichiers exportés dans {moteur.exports()} ; "
                                          f"sauvegarde de la base : {sauvegarde}.")
            elif "exporter" in request.POST:
                if request.POST["exporter"] != "tout":            # un seul fichier : copie dans Exports et téléchargement
                    chemin, _ = moteur.exporter(moteur.PAR_NOM[request.POST["exporter"]], auteur)
                    return FileResponse(open(chemin, "rb"), as_attachment=True, filename=chemin.name)
                for nom in [f.nom for f in moteur.FORMATS]:
                    chemin, n = moteur.exporter(moteur.PAR_NOM[nom], auteur)
                    messages.success(request, f"Exporté : Exports\\{chemin.name} ({n} ligne(s)).")
            elif "convertir" in request.POST:
                dest, n = moteur.convertir_pdf(request.POST["convertir"], request.POST.get("journal", "B1"), auteur)
                messages.success(request, f"PDF converti : Imports\\{dest.name} ({n} ligne(s)). Vérifiez-le, puis importez-le.")
        except moteur.Refus as e:
            messages.error(request, "Refusé : rien n'a été enregistré.")
            for x in e.erreurs[:30]:
                messages.error(request, x)
            if len(e.erreurs) > 30:
                messages.error(request, f"… et {len(e.erreurs) - 30} autre(s) erreur(s).")
        except (KeyError, ValueError, OSError) as e:
            messages.error(request, f"Opération impossible : {e}")
        return redirect("echanges")
    moteur.ecrire_lexiques()
    fichiers = moteur.a_importer()
    return render(request, "compta/echanges.html", {
        "dossier_pc": Reglage.lire("dossier_pc"), "formats": moteur.FORMATS, "imports": moteur.imports(), "exports": moteur.exports(), "sauvegardes": dossiers.sauvegardes(),
        "dossiers": [(c, lib, Reglage.lire(c), moteur.defaut(c), dossiers.chemin(c)) for c, (_, lib) in moteur.REGLAGES_DOSSIERS.items()],
        "a_importer": [(p.name, f) for p, f in fichiers if p.suffix.lower() in moteur.TABLEURS + (".csv",)],
        "pdfs": [p.name for p, _ in fichiers if p.suffix.lower() == ".pdf"],
        "exportes": [(p.name, max(1, p.stat().st_size // 1024)) for p in moteur.fichiers_exportes()],
    })


@login_required
@tresorier
def modeles(request):
    """Kit de démarrage : modèles vierges de tous les fichiers d'import / export, lexique et mode d'emploi (ZIP)."""
    from django.http import HttpResponse
    r = HttpResponse(moteur.kit_modeles(), content_type="application/zip")
    r["Content-Disposition"] = 'attachment; filename="ComptaBB_modeles_vierges.zip"'
    return r


@login_required
@tresorier
def telecharger(request, nom):
    """Télécharge un fichier du dossier Exports (indispensable sur le site, dont les dossiers ne sont pas visibles)."""
    chemin = next((p for p in moteur.fichiers_exportes() if p.name == nom), None)
    if not chemin:
        raise Http404
    return FileResponse(open(chemin, "rb"), as_attachment=True, filename=chemin.name)
