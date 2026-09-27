"""Page Imports / Exports : fichiers .xlsx du dossier Imports à importer, exports vers le dossier Exports."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

from . import echanges as moteur
from .models import Reglage

tresorier = permission_required("compta.parametrer", raise_exception=True)      # référentiels compris : administrateur


@login_required
@tresorier
def echanges(request):
    auteur = request.user.get_username()
    if request.method == "POST":
        try:
            if "dossiers" in request.POST:
                moteur.changer_dossiers({c: request.POST.get(c, "") for c in moteur.REGLAGES_DOSSIERS}, auteur)
                messages.success(request, f"Dossiers enregistrés : Imports = {moteur.imports()} ; Exports = {moteur.exports()}.")
            elif "reinjecter" in request.POST:
                if request.POST.get("confirmation", "").strip().upper() != "REMPLACER":
                    raise moteur.Refus(["Taper REMPLACER pour confirmer la réinjection."])
                comptes_rendus, sauvegarde = moteur.reinjecter(request.user)
                messages.success(request, f"Réinjection terminée (sauvegarde préalable : {sauvegarde.name}).")
                for x in comptes_rendus:
                    messages.info(request, x)
            elif "importer" in request.POST:
                f, texte = moteur.importer(request.POST["importer"], request.user)
                messages.success(request, f"{request.POST['importer']} importé ({f.contenu}) : {texte}. "
                                          f"Le fichier est rangé dans Imports\\{moteur.IMPORTES}.")
            elif "exporter" in request.POST:
                noms = [f.nom for f in moteur.FORMATS] if request.POST["exporter"] == "tout" else [request.POST["exporter"]]
                for nom in noms:
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
        "formats": moteur.FORMATS, "imports": moteur.imports(), "exports": moteur.exports(),
        "dossiers": [(c, lib, Reglage.lire(c), moteur.defaut(c)) for c, (_, lib) in moteur.REGLAGES_DOSSIERS.items()],
        "a_importer": [(p.name, f) for p, f in fichiers if p.suffix.lower() == ".xlsx"],
        "pdfs": [p.name for p, _ in fichiers if p.suffix.lower() == ".pdf"],
    })
