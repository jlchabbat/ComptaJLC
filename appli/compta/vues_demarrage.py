"""Assistant de premier démarrage (voir demarrage.py) : premier administrateur, puis description de l'association."""

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from . import demarrage as moteur

DEVISES = ["₪", "€", "$", "£", "CHF"]


class CompteForm(forms.Form):
    code = forms.CharField(label="Code d'installation", max_length=20,
                           help_text="Affiché par « python manage.py preparer » dans la console du site.")
    identifiant = forms.CharField(label="Identifiant de l'administrateur (nom ou e-mail)", max_length=150)
    mot_de_passe = forms.CharField(label="Mot de passe (12 caractères au moins)", widget=forms.PasswordInput)
    confirmation = forms.CharField(label="Encore une fois", widget=forms.PasswordInput)

    def clean_code(self):
        if not moteur.code_valide(self.cleaned_data["code"]):
            raise ValidationError("Code d'installation incorrect.")
        return self.cleaned_data["code"]

    def clean(self):
        c = super().clean()
        mdp = c.get("mot_de_passe", "")
        if mdp and mdp != c.get("confirmation"):
            self.add_error("confirmation", "Les deux mots de passe sont différents.")
        elif mdp and len(mdp) < 12:
            self.add_error("mot_de_passe", "12 caractères au moins.")
        elif mdp:
            try:
                validate_password(mdp, User(username=c.get("identifiant", "")))
            except ValidationError as e:
                self.add_error("mot_de_passe", e)
        return c


def compte(request):
    """Site neuf, sans aucun utilisateur : création du premier administrateur."""
    if User.objects.exists():
        return redirect("tableau_de_bord")
    moteur.code_installation()                          # le code existe dès la première visite (fichier des données)
    form = CompteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        u = moteur.creer_administrateur(form.cleaned_data["identifiant"].strip(), form.cleaned_data["mot_de_passe"])
        login(request, u, backend=settings.AUTHENTICATION_BACKENDS[0])
        messages.success(request, f"Administrateur « {u.username} » créé. Décrivez maintenant l'association.")
        return redirect("demarrage")
    return render(request, "compta/demarrage_compte.html", {"form": form})


class AssociationForm(forms.Form):
    nom = forms.CharField(label="Nom de l'association", max_length=200)
    devise = forms.CharField(label="Devise (symbole)", max_length=10, initial="€",
                             widget=forms.TextInput(attrs={"list": "devises", "size": 6}))
    plan = forms.ChoiceField(label="Plan comptable", widget=forms.RadioSelect, initial="base", choices=[
        ("base", "Plan de base proposé par ComptaBB (comptes, journaux, codes analytiques), modifiable ensuite"),
        ("importer", "J'importerai mes propres fichiers (plan comptable, journaux, codes…) à partir des modèles vierges")])
    debut = forms.DateField(label="Début du premier exercice", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    fin = forms.DateField(label="Fin du premier exercice", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    caisse = forms.BooleanField(label="Une caisse (espèces)", required=False, initial=True)
    carte = forms.CharField(label="Carte de paiement réglée le mois suivant (nom, ex. Isracard)", max_length=40, required=False,
                            help_text="Vide : pas de carte.")
    hebergeur = forms.CharField(label="Site qui héberge des justificatifs en lien (nom du site)", max_length=40, required=False,
                                help_text="Vide : les justificatifs sont tous déposés sur le site.")
    traductions = forms.BooleanField(label="Relevés en hébreu à traduire en français", required=False)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for i in (1, 2, 3):
            self.fields[f"banque{i}"] = forms.CharField(label=f"Banque {i} (nom)", max_length=60, required=False)
            self.fields[f"format{i}"] = forms.ChoiceField(label="Relevé", choices=moteur.FORMATS_RELEVE, initial="excel")

    def banques(self):
        return [(self[f"banque{i}"], self[f"format{i}"]) for i in (1, 2, 3)]

    def clean(self):
        c = super().clean()
        if c.get("debut") and c.get("fin") and c["fin"] <= c["debut"]:
            self.add_error("fin", "La fin doit suivre le début.")
        c["banques"] = [(c[f"banque{i}"].strip(), c[f"format{i}"]) for i in (1, 2, 3) if c.get(f"banque{i}", "").strip()]
        if c.get("plan") == "base" and not c["banques"] and not c.get("caisse"):
            raise ValidationError("Indiquer au moins une banque ou la caisse.")
        if sum(1 for _, f in c["banques"] if f == "bit") > 1:
            raise ValidationError("Un seul relevé Bit.")
        return c


@login_required
@permission_required("compta.parametrer", raise_exception=True)
def assistant(request):
    if not moteur.a_faire():
        messages.info(request, "L'assistant de premier démarrage a déjà été passé.")
        return redirect("tableau_de_bord")
    debut, fin = moteur.exercice_propose()
    form = AssociationForm(request.POST or None, initial={"debut": debut, "fin": fin})
    if request.method == "POST" and form.is_valid():
        fait = moteur.demarrer(form.cleaned_data, request.user.get_username())
        messages.success(request, "ComptaBB est prêt : " + ", ".join(fait) + ".")
        if form.cleaned_data["plan"] == "importer":
            messages.info(request, "Téléchargez les modèles vierges, remplissez-les dans l'ordre de leur numéro, puis déposez-les ici.")
            return redirect("echanges")
        return redirect("tableau_de_bord")
    return render(request, "compta/demarrage.html", {"form": form, "devises": DEVISES})
