"""Administration › Licence : état de la licence du site et saisie d'une nouvelle licence."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

from . import licence as moteur
from .models import Modification, Reglage


@login_required
@permission_required("compta.parametrer", raise_exception=True)
def licence(request):
    if request.method == "POST":
        texte = "".join(request.POST.get("licence", "").split())
        try:
            lic = moteur.lire(texte)
        except moteur.LicenceInvalide as e:
            messages.error(request, str(e))
        else:
            Reglage.objects.update_or_create(cle="licence", defaults={"valeur": texte, "description": "Licence du site"})
            Modification.objects.create(auteur=request.user.get_username(), lot="Licence", action="Licence enregistrée",
                                        objet=lic["association"][:200], apres=f"site {lic['site']} · fin {lic['fin']:%d/%m/%Y}")
            messages.success(request, f"Licence enregistrée : {lic['association']}, jusqu'au {lic['fin']:%d/%m/%Y}.")
        return redirect("licence")
    return render(request, "compta/licence.html", {"etat": moteur.etat(), "sites": moteur.sites(),
                                                   "active": bool(moteur.CLE_PUBLIQUE)})
