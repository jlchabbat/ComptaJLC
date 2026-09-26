"""Suivi des membres : liste, fiche (situation, historique, lettrage, relance), impayés, cotisations."""

import csv
import io
from urllib.parse import quote

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from . import membres as moteur
from .models import ZERO, Exercice, Ligne, Membre, Modification, arrondi

voir = permission_required("compta.view_membre", raise_exception=True)
gerer = permission_required("compta.change_membre", raise_exception=True)


class MembreFicheForm(forms.ModelForm):
    class Meta:
        model = Membre
        fields = ["type", "nom", "prenom", "adresse", "code_postal", "ville", "telephone", "email", "date_adhesion", "statut",
                  "cotisation"]
        widgets = {"date_adhesion": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class ImportMembresForm(forms.Form):
    fichier = forms.FileField(label="Fichier des membres (CSV, modèle 07_membres.csv)")


@login_required
@voir
def liste(request):
    peut = request.user.has_perm("compta.change_membre")
    form = ImportMembresForm(request.POST or None, request.FILES or None) if peut else None
    if request.method == "POST" and peut:
        if "lettrage_auto" in request.POST:
            n = sum(moteur.lettrage_automatique(m.compte) for m in Membre.objects.select_related("compte"))
            Modification.objects.create(auteur=request.user.get_username(), lot="Membres", action="Lettrage automatique",
                                        objet="tous les membres", apres=f"{n} lettrage(s)")
            messages.success(request, f"{n} lettrage(s) automatique(s).")
            return redirect("membres")
        if form.is_valid():
            s = form.cleaned_data["fichier"].read().decode("utf-8-sig", errors="replace")
            maj, inconnus = moteur.importer_csv(list(csv.reader(io.StringIO(s), delimiter=";" if s.count(";") >= s.count(",") else ",")))
            Modification.objects.create(auteur=request.user.get_username(), lot="Membres", action="Import membres",
                                        objet=form.cleaned_data["fichier"].name[:200], apres=f"{maj} fiche(s)")
            messages.success(request, f"{maj} fiche(s) mise(s) à jour." + (f" Comptes inconnus ignorés : {', '.join(inconnus[:10])}." if inconnus else ""))
            return redirect("membres")
    q, statut, type_ = request.GET.get("q", "").strip(), request.GET.get("statut", ""), request.GET.get("type", "")
    qs = Membre.objects.select_related("compte", "type")
    if q:
        qs = qs.filter(Q(nom__icontains=q) | Q(prenom__icontains=q) | Q(compte__numero__icontains=q) | Q(email__icontains=q)
                       | Q(ville__icontains=q))
    if statut:
        qs = qs.filter(statut=statut)
    if type_.isdigit():
        qs = qs.filter(type_id=type_)
    soldes = dict(Ligne.objects.filter(compte__in=[m.compte_id for m in qs]).exclude(mouvement__origine="cloture")
                  .values("compte").annotate(s=Sum("debit") - Sum("credit")).values_list("compte", "s"))
    lignes = [(m, arrondi(soldes.get(m.compte_id) or ZERO)) for m in qs]
    from .models import TypeTiers
    return render(request, "compta/membres.html", {"lignes": lignes, "q": q, "statut": statut, "statuts": Membre.STATUTS,
                                                    "type": type_, "types": TypeTiers.objects.all(),
                                                    "peut": peut, "import_form": form,
                                                    "total_du": sum((s for _, s in lignes if s > 0), ZERO)})


@login_required
@voir
def fiche(request, numero):
    m = get_object_or_404(Membre.objects.select_related("compte"), compte__numero=numero)
    peut = request.user.has_perm("compta.change_membre")
    form = MembreFicheForm(request.POST if "enregistrer" in request.POST else None, instance=m) if peut else None
    if request.method == "POST" and peut:
        auteur = request.user.get_username()
        try:
            if "enregistrer" in request.POST:
                if form.is_valid():
                    form.save()
                    Modification.objects.create(auteur=auteur, lot="Membres", action="Fiche membre", objet=f"{m.compte_id} {m}")
                    messages.success(request, "Fiche enregistrée.")
                    return redirect("membre", numero)
            elif "lettrer" in request.POST:
                code = moteur.lettrer(m.compte, Ligne.objects.filter(compte=m.compte, pk__in=request.POST.getlist("ligne")), auteur)
                messages.success(request, f"Lettré : {code}.")
                return redirect("membre", numero)
            elif "delettrer" in request.POST:
                moteur.delettrer(m.compte, request.POST["delettrer"], auteur)
                messages.success(request, f"Lettrage {request.POST['delettrer']} annulé.")
                return redirect("membre", numero)
            elif "lettrage_auto" in request.POST:
                n = moteur.lettrage_automatique(m.compte, auteur)
                messages.success(request, f"{n} lettrage(s) automatique(s).")
                return redirect("membre", numero)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("membre", numero)
    s = moteur.situation(m.compte)
    historique, cumul = [], ZERO
    for l in (Ligne.objects.filter(compte=m.compte).exclude(mouvement__origine="cloture").select_related("mouvement")
              .order_by("mouvement__date", "mouvement__numero", "ordre")):
        cumul += l.debit - l.credit
        historique.append((l, cumul))
    relance = moteur.texte_relance(m, s) if s.solde > 0 else ""
    return render(request, "compta/membre.html", {
        "m": m, "s": s, "form": form, "peut": peut, "historique": historique, "relance": relance,
        "mailto": f"mailto:{m.email}?subject={quote('Loge Bnei Brith – votre compte')}&body={quote(relance)}" if relance and m.email else "",
    })


@login_required
@voir
def impayes(request):
    lignes = moteur.impayes()
    return render(request, "compta/impayes.html", {
        "lignes": lignes, "total": sum((s.solde for _, s in lignes), ZERO),
        "tranches": [(lib, sum((s.tranches[i][1] for _, s in lignes), ZERO)) for i, (lib, _) in enumerate(moteur.TRANCHES)]})


@login_required
@voir
def cotisations(request):
    pk = request.GET.get("exercice", "")
    ex = (Exercice.objects.filter(pk=pk).first() if pk.isdigit() else None) or Exercice.ouvert() or Exercice.objects.last()
    lignes, total = moteur.cotisations(ex) if ex else ([], {})
    return render(request, "compta/cotisations.html", {"exercice": ex, "exercices": Exercice.objects.order_by("-debut"),
                                                        "lignes": lignes, "total": total})
