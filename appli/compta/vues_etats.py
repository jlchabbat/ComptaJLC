"""États annuels, budget et clôture de l'exercice (Lot 4)."""

import io

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from . import cloture as moteur
from . import etats
from .export import classeur_exercice
from .forms import cherchable
from .models import Budget, CodeAnalytique, Compte, Exercice, Modification
from .reglages import montant

consulter = permission_required("compta.view_mouvement", raise_exception=True)


def exercice_choisi(request):
    pk = request.GET.get("exercice")
    ex = Exercice.objects.filter(pk=pk).first() if pk and pk.isdigit() else None
    return ex or Exercice.ouvert() or Exercice.objects.order_by("-debut").first()


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["nature", "compte", "anal1", "anal2", "montant"]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["compte"].queryset = etats.comptes_sans_budget()
        self.fields["anal1"].queryset = CodeAnalytique.objects.filter(axe=1)
        self.fields["anal2"].queryset = CodeAnalytique.objects.filter(axe=2)
        self.fields["montant"].min_value = 0
        for n in ("compte", "anal1", "anal2"):
            self.fields[n].help_text = "Un seul des trois : compte, axe 1 ou axe 2."
        cherchable(self)

    def clean(self):
        c = super().clean()
        if sum(1 for n in ("compte", "anal1", "anal2") if c.get(n)) != 1:
            raise forms.ValidationError("Choisir exactement un compte, un code d'axe 1 ou un code d'axe 2.")
        if c.get("compte") and c["compte"].numero[0] != ("6" if c.get("nature") == "C" else "7"):
            raise forms.ValidationError("Charges : compte de classe 6 ; produits : compte de classe 7.")
        return c


@login_required
@consulter
def etats_annuels(request):
    ex = exercice_choisi(request)
    if not ex:
        return render(request, "compta/etats.html", {})
    prec = etats.precedent(ex)
    budget_form = None
    if request.user.has_perm("compta.add_budget"):
        budget_form = BudgetForm(request.POST if "ajouter_budget" in request.POST else None, prefix="budget")
        if request.method == "POST":
            if "ajouter_budget" in request.POST and budget_form.is_valid():
                b = budget_form.save(commit=False)
                b.exercice = ex
                b.save()
                messages.success(request, f"Budget ajouté : {b.cible} {montant(b.montant)}.")
                return redirect(f"{request.path}?exercice={ex.pk}#budget")
            if "supprimer_budget" in request.POST:
                Budget.objects.filter(pk=request.POST["supprimer_budget"], exercice=ex).delete()
                messages.success(request, "Ligne de budget supprimée.")
                return redirect(f"{request.path}?exercice={ex.pk}#budget")
    bilan_n1 = etats.bilan(prec.fin, prec.debut) if prec else None
    return render(request, "compta/etats.html", {
        "exercice": ex, "precedent": prec, "exercices": Exercice.objects.order_by("-debut"),
        "cr": etats.compte_de_resultat(ex, prec),
        "axes": [("Résultat par axe 1 (nature)", etats.par_axe(ex, prec, 1)), ("Résultat par axe 2 (événement, projet)", etats.par_axe(ex, prec, 2))],
        "bilan": etats.comparer(etats.bilan(ex.fin, ex.debut), bilan_n1), "bilan_n1": bilan_n1,
        "budget": etats.budget(ex), "budget_form": budget_form,
    })


@login_required
@consulter
def export_etats(request):
    ex = exercice_choisi(request)
    if not ex:
        raise Http404
    tampon = io.BytesIO()
    classeur_exercice(ex).save(tampon)
    nom = f"ComptaBB_etats_{ex.libelle}".replace(" ", "_").replace("/", "-").replace("–", "-") + ".xlsx"
    from .dossiers import copier_export
    copier_export(nom, tampon.getvalue())
    return HttpResponse(tampon.getvalue(), headers={
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "Content-Disposition": f'attachment; filename="{nom}"'})


class ClotureForm(forms.Form):
    confirmation = forms.BooleanField(label="J'ai vérifié les états et je clôture définitivement l'exercice")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        cherchable(self)


@login_required
@permission_required("compta.change_exercice", raise_exception=True)
def cloture(request):
    ex = moteur.premier_non_clos()
    prep = moteur.preparer(ex) if ex else None
    form = ClotureForm(request.POST or None)
    if request.method == "POST" and ex and form.is_valid():
        try:
            moteur.cloturer(ex, request.user)
        except ValueError as e:
            messages.error(request, f"Clôture refusée : {e}")
        else:
            messages.success(request, f"Exercice « {ex.libelle} » clôturé. Résultat affecté : {etats.montant(ex.resultat)}.")
        return redirect("cloture")
    comptes = {c.numero: c.libelle for c in Compte.objects.filter(numero__in=[n for n, _, _ in prep.lignes])} if prep else {}
    return render(request, "compta/cloture.html", {
        "exercice": ex, "prep": prep, "form": form, "comptes": comptes,
        "total_an": sum(d for _, d, _ in prep.lignes) if prep else 0,
        "clos": Exercice.objects.filter(clos=True).order_by("-debut"),
        "bilan": etats.bilan(ex.fin, ex.debut) if ex else None,
    })


@login_required
@consulter
def archive(request, pk):
    ex = get_object_or_404(Exercice, pk=pk, clos=True)
    chemin = moteur.dossier_archives() / ex.archive if ex.archive else None
    if not chemin or not chemin.exists():
        raise Http404("Archive introuvable.")
    Modification.objects.create(auteur=request.user.get_username(), lot="Clôture", action="Téléchargement", objet=ex.archive)
    return FileResponse(open(chemin, "rb"), as_attachment=True, filename=ex.archive)
