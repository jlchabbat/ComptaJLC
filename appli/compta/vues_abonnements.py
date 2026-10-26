"""Modèles d'écritures et abonnements (menu Saisie)."""

import datetime as dt

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from . import abonnements as moteur
from .models import Abonnement, ModeleEcriture, Mouvement

saisir = permission_required("compta.add_mouvement", raise_exception=True)


class AbonnementForm(forms.ModelForm):
    class Meta:
        model = Abonnement
        fields = ["modele", "periodicite", "jour", "debut", "fin"]
        widgets = {"debut": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["modele"].queryset = ModeleEcriture.objects.filter(actif=True)

    def clean_jour(self):
        j = self.cleaned_data["jour"]
        if not 1 <= j <= 31:
            raise forms.ValidationError("Jour de 1 à 31.")
        return j


@login_required
@saisir
def page(request):
    form = AbonnementForm(request.POST if "ajouter" in request.POST else None, prefix="ab")
    if request.method == "POST":
        if "generer" in request.POST:
            try:
                jusquau = dt.date.fromisoformat(request.POST.get("jusquau", ""))
            except ValueError:
                jusquau = dt.date.today()
            crees, erreurs = moteur.generer(jusquau, request.user)
            if crees:
                messages.success(request, f"{len(crees)} écriture(s) générée(s) : Mvt {', '.join(str(m.numero) for m in crees)}.")
            elif not erreurs:
                messages.info(request, f"Aucune échéance à générer jusqu'au {jusquau:%d/%m/%Y}.")
            for e in erreurs:
                messages.error(request, e)
            return redirect("abonnements")
        if "ajouter" in request.POST and form.is_valid():
            a = form.save()
            messages.success(request, f"Abonnement « {a} » créé ; prochaine échéance {moteur.prochaine(a):%d/%m/%Y}.")
            return redirect("abonnements")
        if "suspendre" in request.POST:
            a = get_object_or_404(Abonnement, pk=request.POST["suspendre"])
            a.actif = not a.actif
            a.save(update_fields=["actif"])
            return redirect("abonnements")
        if "supprimer_abonnement" in request.POST:
            Abonnement.objects.filter(pk=request.POST["supprimer_abonnement"]).delete()
            messages.success(request, "Abonnement supprimé (les écritures déjà générées restent).")
            return redirect("abonnements")
        if "supprimer_modele" in request.POST:
            m = get_object_or_404(ModeleEcriture, pk=request.POST["supprimer_modele"])
            if m.abonnements.exists():
                messages.error(request, f"Le modèle « {m} » sert à un abonnement : supprimer d'abord l'abonnement.")
            else:
                m.delete()
                messages.success(request, f"Modèle « {m.nom} » supprimé.")
            return redirect("abonnements")
    abonnements = [(a, moteur.prochaine(a)) for a in Abonnement.objects.select_related("modele__journal")]
    return render(request, "compta/abonnements.html", {
        "modeles": ModeleEcriture.objects.prefetch_related("lignes__compte").select_related("journal"),
        "abonnements": abonnements, "form": form, "aujourdhui": dt.date.today()})


@login_required
@saisir
def depuis_mouvement(request, numero):
    """Enregistre un Mvt comme modèle (bouton de la fiche du mouvement)."""
    m = get_object_or_404(Mouvement, numero=numero)
    if request.method == "POST":
        try:
            modele = moteur.depuis_mouvement(m, request.POST.get("nom", ""))
            messages.success(request, f"Modèle « {modele} » créé depuis le Mvt {m.numero}.")
            return redirect("abonnements")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect("mouvement", numero)
