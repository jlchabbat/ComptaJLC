"""Modifier ou contrepasser un mouvement, saisir une écriture libre (trésorier)."""

import datetime as dt
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from . import corrections as moteur
from .forms import EnteteMouvementForm, LignesMouvementFormSet
from .models import Mouvement

corriger = permission_required("compta.change_mouvement", raise_exception=True)


def lire_lignes(formset):
    res = []
    for f in formset.forms:
        c = f.cleaned_data
        if not c or c.get("DELETE") or f.vide():
            continue
        res.append(moteur.LigneSaisie(c.get("id"), c["compte"], c.get("libelle") or "", c.get("debit") or Decimal("0"),
                                      c.get("credit") or Decimal("0"), c["anal2"]))
    return res


def editer(request, m=None):
    if request.method == "POST":
        entete = EnteteMouvementForm(request.POST)
        formset = LignesMouvementFormSet(request.POST, prefix="l")
        if entete.is_valid() and formset.is_valid():
            c = entete.cleaned_data
            try:
                if m:
                    moteur.modifier(m, c["date"], c["journal"], lire_lignes(formset), c["motif"], request.user)
                    messages.success(request, f"Mouvement {m.numero} modifié.")
                else:
                    m = moteur.creer(c["date"], c["journal"], lire_lignes(formset), c["motif"], request.user)
                    messages.success(request, f"Mouvement {m.numero} créé.")
                return redirect("mouvement", m.numero)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        if m:
            entete = EnteteMouvementForm(initial={"date": m.date, "journal": m.journal_id})
            formset = LignesMouvementFormSet(prefix="l", initial=[
                {"id": l.pk, "compte": l.compte_id, "libelle": l.libelle, "debit": l.debit or None, "credit": l.credit or None,
                 "anal2": l.anal2_id} for l in m.lignes.all()])
        else:
            entete = EnteteMouvementForm(initial={"date": dt.date.today()})
            formset = LignesMouvementFormSet(prefix="l")
    return render(request, "compta/mouvement_edition.html", {"m": m, "entete": entete, "formset": formset})


@login_required
@corriger
def modifier(request, numero):
    m = get_object_or_404(Mouvement, numero=numero)
    if moteur.verrou(m):
        messages.error(request, moteur.verrou(m))
        return redirect("mouvement", numero)
    return editer(request, m)


@login_required
@permission_required("compta.add_mouvement", raise_exception=True)
def nouveau(request):
    return editer(request)


class ContrepassationForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="Date de l'annulation")
    motif = forms.CharField(max_length=150)


@login_required
@corriger
def contrepasser(request, numero):
    m = get_object_or_404(Mouvement, numero=numero)
    form = ContrepassationForm(request.POST or None, initial={"date": moteur.date_par_defaut(m)})
    if request.method == "POST" and form.is_valid():
        try:
            inverse = moteur.contrepasser(m, form.cleaned_data["date"], form.cleaned_data["motif"], request.user)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(request, f"Mouvement {m.numero} annulé par le mouvement {inverse.numero}.")
            return redirect("mouvement", inverse.numero)
    return render(request, "compta/contrepassation.html", {"m": m, "form": form})
