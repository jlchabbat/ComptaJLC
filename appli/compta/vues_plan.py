"""Plan comptable, journaux et codes d'axe : écrans guidés de l'administrateur (remplacent l'administration technique)."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render

from .models import CodeAnalytique, Compte, Journal, Modification

administrer = permission_required("compta.parametrer", raise_exception=True)
# plan comptable et codes d'axe : administrateur et gestion (pas le bénévole ni la consultation) ; journaux : administrateur
gerer_plan = permission_required(["compta.add_compte", "compta.change_compte", "compta.delete_compte"], raise_exception=True)
gerer_codes = permission_required(["compta.add_codeanalytique", "compta.change_codeanalytique", "compta.delete_codeanalytique"],
                                  raise_exception=True)
TYPES_JOURNAL = [("AN", "AN – à-nouveaux"), ("BQ", "BQ – banque"), ("CA", "CA – caisse"), ("OD", "OD – opérations diverses"),
                 ("HA", "HA – achats"), ("VE", "VE – ventes")]


class CompteForm(forms.ModelForm):
    class Meta:
        model = Compte
        fields = ["numero", "libelle", "anal1", "lettrable", "actif"]
        labels = {"numero": "Compte", "anal1": "Axe 1 (nature)", "lettrable": "Compte de tiers (lettrable)", "actif": "Proposé en saisie"}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["anal1"].queryset = CodeAnalytique.objects.filter(axe=1)
        self.fields["anal1"].empty_label = "(aucun)"
        if self.instance.pk:
            self.fields["numero"].disabled = True

    def clean_numero(self):
        return self.cleaned_data["numero"].strip()


class JournalForm(forms.ModelForm):
    class Meta:
        model = Journal
        fields = ["code", "intitule", "type", "compte", "actif"]
        labels = {"code": "Code", "intitule": "Intitulé", "type": "Type", "compte": "Compte de trésorerie", "actif": "Utilisé"}

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        types = list(TYPES_JOURNAL)
        actuel = self.instance.type if self.instance.pk else ""
        if actuel and actuel not in dict(types):
            types.append((actuel, actuel))
        self.fields["type"] = forms.ChoiceField(label="Type", choices=[("", "(aucun)")] + types, required=False)
        self.fields["compte"].empty_label = "(aucun)"
        if self.instance.pk:
            self.fields["code"].disabled = True

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class CodeForm(forms.ModelForm):
    class Meta:
        model = CodeAnalytique
        fields = ["libelle", "statut"]
        labels = {"libelle": "Libellé", "statut": "Statut"}


def _trace(request, action, objet, avant="", apres=""):
    Modification.objects.create(auteur=request.user.get_username(), lot="Paramétrage", action=action, objet=objet[:200],
                                avant=avant[:300], apres=apres[:300])


def _fiche(request, modele, form_classe, cle, valeur, retour, titre, libelle, suppression=True):
    suppression = suppression and request.user.has_perm(f"compta.delete_{modele._meta.model_name}")
    obj = get_object_or_404(modele, **{cle: valeur}) if valeur else None
    form = form_classe(request.POST or None, instance=obj)
    if request.method == "POST":
        if "supprimer" in request.POST and obj and suppression:
            try:
                obj.delete()
            except ProtectedError:
                messages.error(request, "Suppression impossible : utilisé par des écritures ou d'autres éléments. Décochez plutôt « utilisé / proposé ».")
            else:
                _trace(request, "Suppression", f"{libelle} {valeur}")
                messages.success(request, f"{libelle.capitalize()} {valeur} supprimé.")
                return redirect(retour)
        elif form.is_valid():
            nouveau = obj is None
            if not nouveau:
                avant = str(modele.objects.get(pk=obj.pk).__dict__.get("libelle") or modele.objects.get(pk=obj.pk).__dict__.get("intitule", ""))
            saved = form.save()
            _trace(request, "Création" if nouveau else "Modification", f"{libelle} {saved.pk}", "" if nouveau else avant, str(saved))
            messages.success(request, f"{libelle.capitalize()} {saved.pk} {'créé' if nouveau else 'enregistré'}.")
            return redirect(retour)
    return render(request, "compta/parametrage_fiche.html", {"form": form, "obj": obj, "titre": titre, "retour": retour,
                                                             "suppression": suppression and obj is not None})


@login_required
@gerer_plan
def plan(request):
    q = request.GET.get("q", "").strip()
    comptes = Compte.objects.select_related("anal1").order_by("numero")
    if q:
        comptes = comptes.filter(Q(numero__startswith=q) | Q(libelle__icontains=q))
    return render(request, "compta/plan.html", {"comptes": comptes, "q": q})


@login_required
@gerer_plan
def compte(request, numero=None):
    return _fiche(request, Compte, CompteForm, "numero", numero, "plan", f"Compte {numero}" if numero else "Nouveau compte", "compte")


@login_required
@administrer
def journaux_param(request):
    return render(request, "compta/journaux_param.html", {"journaux": Journal.objects.select_related("compte").order_by("code")})


@login_required
@administrer
def journal(request, code=None):
    return _fiche(request, Journal, JournalForm, "code", code, "journaux_param", f"Journal {code}" if code else "Nouveau journal", "journal")


@login_required
@gerer_codes
def axes_param(request):
    return render(request, "compta/axes_param.html", {"codes": CodeAnalytique.objects.order_by("axe", "code")})


@login_required
@gerer_codes
def code_axe(request, code):
    return _fiche(request, CodeAnalytique, CodeForm, "code", code, "axes_param", f"Code {code}", "code")
