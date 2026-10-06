"""Tiers : liste, fiche (situation, historique, lettrage)."""

import io

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import tiers as moteur
from .models import ZERO, Ligne, Modification, Tiers, arrondi

voir = permission_required("compta.view_tiers", raise_exception=True)
gerer = permission_required("compta.change_tiers", raise_exception=True)


class TiersFicheForm(forms.ModelForm):
    class Meta:
        model = Tiers
        fields = ["type", "nom", "prenom", "adresse", "code_postal", "ville", "telephone", "email"]


class ImportTiersForm(forms.Form):
    fichier = forms.FileField(label="Fichier des tiers (Tiers.xlsx ou CSV)")


@login_required
@voir
def liste(request):
    peut = request.user.has_perm("compta.change_tiers")
    peut_importer = request.user.has_perm("compta.echanger_fichiers")
    form = ImportTiersForm(request.POST or None, request.FILES or None) if peut_importer else None
    if request.method == "POST" and (peut or peut_importer):
        if "lettrage_auto" in request.POST and peut:
            n = sum(moteur.lettrage_automatique(m.compte) for m in Tiers.objects.select_related("compte"))
            Modification.objects.create(auteur=request.user.get_username(), lot="Tiers", action="Lettrage automatique",
                                        objet="tous les tiers", apres=f"{n} lettrage(s)")
            messages.success(request, f"{n} lettrage(s) automatique(s).")
            return redirect("tiers")
        if form is not None and form.is_valid():
            f = form.cleaned_data["fichier"]
            try:
                r = moteur.importer_tableau(moteur.lire_tableau(f.name, f.read()))
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("tiers")
            Modification.objects.create(auteur=request.user.get_username(), lot="Tiers", action="Import tiers", objet=f.name[:200],
                                        apres=f"{len(r.crees)} créé(s), {len(r.mis_a_jour)} mis à jour, {len(r.erreurs)} erreur(s)")
            messages.success(request, f"Import de {f.name} : {len(r.crees)} tiers créé(s), {len(r.mis_a_jour)} mis à jour.")
            if r.crees:
                messages.info(request, "Créés : " + " · ".join(r.crees[:30]) + (" …" if len(r.crees) > 30 else ""))
            for e in r.erreurs[:20]:
                messages.error(request, e)
            return redirect("tiers")
    q, type_ = request.GET.get("q", "").strip(), request.GET.get("type", "")
    qs = Tiers.objects.select_related("compte", "type")
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(compte__numero__icontains=q) | Q(email__icontains=q)
                       | Q(ville__icontains=q))
    if type_.isdigit():
        qs = qs.filter(type_id=type_)
    soldes = dict(Ligne.objects.filter(compte__in=[m.compte_id for m in qs]).exclude(mouvement__origine="cloture")
                  .values("compte").annotate(s=Sum("debit") - Sum("credit")).values_list("compte", "s"))
    lignes = [(m, arrondi(soldes.get(m.compte_id) or ZERO)) for m in qs]
    from .models import TypeTiers
    return render(request, "compta/tiers.html", {"lignes": lignes, "q": q,
                                                    "type": type_, "types": TypeTiers.objects.all(),
                                                    "peut": peut, "peut_importer": peut_importer, "import_form": form,
                                                    "total_du": sum((s for _, s in lignes if s > 0), ZERO)})


@login_required
@voir
def fiche(request, numero):
    m = get_object_or_404(Tiers.objects.select_related("compte"), compte__numero=numero)
    peut = request.user.has_perm("compta.change_tiers")
    form = TiersFicheForm(request.POST if "enregistrer" in request.POST else None, instance=m) if peut else None
    if request.method == "POST" and peut:
        auteur = request.user.get_username()
        try:
            if "enregistrer" in request.POST:
                if form.is_valid():
                    form.save()
                    Modification.objects.create(auteur=auteur, lot="Tiers", action="Fiche tiers", objet=f"{m.compte_id} {m}")
                    messages.success(request, "Fiche enregistrée.")
                    return redirect("tiers_fiche", numero)
            elif "lettrer" in request.POST:
                code = moteur.lettrer(m.compte, Ligne.objects.filter(compte=m.compte, pk__in=request.POST.getlist("ligne")), auteur)
                messages.success(request, f"Lettré : {code}.")
                return redirect("tiers_fiche", numero)
            elif "delettrer" in request.POST:
                moteur.delettrer(m.compte, request.POST["delettrer"], auteur)
                messages.success(request, f"Lettrage {request.POST['delettrer']} annulé.")
                return redirect("tiers_fiche", numero)
            elif "lettrage_auto" in request.POST:
                n = moteur.lettrage_automatique(m.compte, auteur)
                messages.success(request, f"{n} lettrage(s) automatique(s).")
                return redirect("tiers_fiche", numero)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("tiers_fiche", numero)
    s = moteur.situation(m.compte)
    historique, cumul = [], ZERO
    for l in (Ligne.objects.filter(compte=m.compte).exclude(mouvement__origine="cloture").select_related("mouvement")
              .order_by("mouvement__date", "mouvement__numero", "ordre")):
        cumul += l.debit - l.credit
        historique.append((l, cumul))
    return render(request, "compta/tiers_fiche.html", {
        "m": m, "s": s, "form": form, "peut": peut, "historique": historique,
    })


@login_required
@voir
def modele_tiers(request):
    tampon = io.BytesIO()
    moteur.classeur_modele().save(tampon)
    return HttpResponse(tampon.getvalue(), headers={
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": 'attachment; filename="Tiers.xlsx"'})
