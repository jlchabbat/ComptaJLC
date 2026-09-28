"""Documents intégrés à l'application (menu Éditions) : Présentation, Mode d'emploi, Installation et mises à jour, en PDF.

Ils sont produits par deploiement/documentation.py et livrés avec le code : chaque mise à jour les met à jour."""

from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404

DOSSIER = Path(__file__).resolve().parent / "documentation"
DOCUMENTS = {"presentation": "ComptaBB_presentation.pdf", "mode-emploi": "ComptaBB_mode_emploi.pdf",
             "installation": "ComptaBB_installation.pdf"}


@login_required
def document(request, nom):
    chemin = DOSSIER / DOCUMENTS.get(nom, "")
    if nom not in DOCUMENTS or not chemin.is_file():
        raise Http404("Document absent.")
    if nom == "installation" and not request.user.has_perm("compta.parametrer"):      # réinstallation : administrateur
        raise PermissionDenied
    return FileResponse(open(chemin, "rb"), content_type="application/pdf", filename=chemin.name,
                        as_attachment="telecharger" in request.GET)
