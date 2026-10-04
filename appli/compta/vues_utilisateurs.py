"""Comptes de connexion : « Mon compte » pour chacun, page Utilisateurs pour l'administrateur.

L'identifiant peut être un nom (sans espace) ou une adresse e-mail ; on se connecte aussi avec l'e-mail enregistré.
Profils, du plus large au plus restreint : Administration (paramétrage de base, utilisateurs, base de données),
Gestion (tout sauf le paramétrage de base), Consultation (consultation seule), Bénévole (la liaison : ses fiches seulement)."""

from django import forms
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .apps import ROLES
from .forms import identifiant_libre
from .models import Modification

ROLES_CREES_ICI = [r for r in ROLES if r != "Bénévole"]       # un bénévole se crée depuis Fiches bénévoles (il doit être membre)


class ConnexionParEmail(ModelBackend):
    """Connexion avec l'identifiant (majuscules indifférentes) ou, à défaut, avec l'adresse e-mail enregistrée."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        username = (username or "").strip()
        u = super().authenticate(request, username=username, password=password, **kwargs)
        if u is None and username:
            trouve = User.objects.filter(username__iexact=username).first()        # « Jean » pour « jean »
            if trouve and trouve.check_password(password) and self.user_can_authenticate(trouve):
                return trouve
        if u is None and username and "@" in username:
            trouve = User.objects.filter(email__iexact=username.strip()).first()
            if trouve and trouve.check_password(password) and self.user_can_authenticate(trouve):
                return trouve
        return u


def role(u):
    if u.is_superuser:
        return "Administration"
    return next((g.name for g in u.groups.all() if g.name in ROLES), "—")


def donner_role(u, nom):
    """Un seul rôle par utilisateur ; l'administrateur a aussi les accès « superutilisateur » (Référentiels, base)."""
    u.groups.remove(*Group.objects.filter(name__in=ROLES))
    u.groups.add(Group.objects.get(name=nom))
    u.is_superuser = u.is_staff = nom == "Administration"
    u.save()


def journaliser(request, action, objet, avant="", apres=""):
    Modification.objects.create(auteur=request.user.get_username(), lot="Utilisateurs", action=action, objet=objet[:200],
                                avant=avant[:300], apres=apres[:300])


class IdentifiantForm(forms.Form):
    identifiant = forms.CharField(max_length=150, help_text="Un nom sans espace, ou une adresse e-mail.")
    prenom = forms.CharField(max_length=60, required=False, label="Prénom")
    nom = forms.CharField(max_length=60, required=False)
    email = forms.EmailField(required=False, label="E-mail", help_text="Permet aussi de se connecter.")

    def __init__(self, *a, utilisateur, **k):
        super().__init__(*a, **k)
        self.utilisateur = utilisateur

    def clean_identifiant(self):
        return identifiant_libre(self.cleaned_data["identifiant"], sauf=self.utilisateur)

    def clean_email(self):
        v = self.cleaned_data["email"].strip()
        if v and User.objects.exclude(pk=self.utilisateur.pk).filter(email__iexact=v).exists():
            raise forms.ValidationError("Cette adresse est déjà celle d'un autre utilisateur.")
        if v and User.objects.exclude(pk=self.utilisateur.pk).filter(username__iexact=v).exists():
            raise forms.ValidationError("Cette adresse est l'identifiant d'un autre utilisateur.")
        return v


@login_required
def mon_compte(request):
    u = request.user
    ident = IdentifiantForm(request.POST if "identifiant_maj" in request.POST else None, utilisateur=u,
                            initial={"identifiant": u.username, "prenom": u.first_name, "nom": u.last_name,
                                     "email": u.email}, prefix="id")
    mdp = PasswordChangeForm(u, request.POST if "mot_de_passe_maj" in request.POST else None, prefix="mdp")
    if "identifiant_maj" in request.POST and ident.is_valid():
        c = ident.cleaned_data
        avant = f"{u.username} / {u.get_full_name()} / {u.email}"
        u.username, u.first_name, u.last_name, u.email = c["identifiant"], c.get("prenom", ""), c.get("nom", ""), c["email"]
        u.save(update_fields=["username", "first_name", "last_name", "email"])
        journaliser(request, "Identifiant changé", f"utilisateur {u.pk}", avant=avant,
                    apres=f"{u.username} / {u.get_full_name()} / {u.email}")
        messages.success(request, f"Identifiant enregistré : connectez-vous désormais avec « {u.username} ».")
        return redirect("mon_compte")
    if "mot_de_passe_maj" in request.POST and mdp.is_valid():
        mdp.save()
        update_session_auth_hash(request, mdp.user)
        journaliser(request, "Mot de passe changé", f"utilisateur {u.username}")
        messages.success(request, "Mot de passe changé.")
        return redirect("mon_compte")
    return render(request, "compta/mon_compte.html", {"ident": ident, "mdp": mdp, "role": role(u)})


# ---------------------------------------------------------------- administrateur

class NouvelUtilisateurForm(forms.Form):
    identifiant = forms.CharField(max_length=150, help_text="Un nom sans espace, ou une adresse e-mail.")
    prenom = forms.CharField(max_length=60, required=False, label="Prénom")
    nom = forms.CharField(max_length=60, required=False)
    email = forms.EmailField(required=False, label="E-mail")
    role = forms.ChoiceField(choices=[(r, r) for r in ROLES_CREES_ICI], initial="Gestion", label="Rôle")
    mot_de_passe = forms.CharField(widget=forms.PasswordInput(render_value=True), label="Mot de passe",
                                   help_text="À transmettre à l'utilisateur, qui pourra le changer (Mon compte).")

    clean_identifiant = lambda self: identifiant_libre(self.cleaned_data["identifiant"])  # noqa: E731

    def clean(self):
        c = super().clean()
        if c.get("mot_de_passe"):
            try:
                validate_password(c["mot_de_passe"])
            except forms.ValidationError as e:
                self.add_error("mot_de_passe", e)
        return c


class ModifierUtilisateurForm(forms.Form):
    identifiant = forms.CharField(max_length=150)
    prenom = forms.CharField(max_length=60, required=False, label="Prénom")
    nom = forms.CharField(max_length=60, required=False)
    email = forms.EmailField(required=False, label="E-mail")
    role = forms.ChoiceField(choices=[(r, r) for r in ROLES], label="Rôle")
    actif = forms.BooleanField(required=False, label="Peut se connecter")
    mot_de_passe = forms.CharField(required=False, widget=forms.PasswordInput, label="Nouveau mot de passe",
                                   help_text="Vide = inchangé.")

    def __init__(self, *a, utilisateur, **k):
        super().__init__(*a, **k)
        self.utilisateur = utilisateur

    def clean_identifiant(self):
        return identifiant_libre(self.cleaned_data["identifiant"], sauf=self.utilisateur)

    clean_email = IdentifiantForm.clean_email

    def clean(self):
        c = super().clean()
        u = self.utilisateur
        if u.is_superuser and (c.get("role") != "Administration" or not c.get("actif")):
            if not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=u.pk).exists():
                raise forms.ValidationError("Il faut garder au moins un administrateur actif.")
        if c.get("mot_de_passe"):
            try:
                validate_password(c["mot_de_passe"], u)
            except forms.ValidationError as e:
                self.add_error("mot_de_passe", e)
        return c


def administrateur(request):
    if not request.user.is_superuser:
        raise PermissionDenied


@login_required
def utilisateurs(request):
    administrateur(request)
    nouveau = NouvelUtilisateurForm(request.POST if "creer" in request.POST else None, prefix="n")
    if "creer" in request.POST and nouveau.is_valid():
        c = nouveau.cleaned_data
        with transaction.atomic():
            u = User.objects.create_user(c["identifiant"], email=c["email"], password=c["mot_de_passe"], first_name=c["prenom"],
                                         last_name=c["nom"])
            donner_role(u, c["role"])
        journaliser(request, "Création", f"utilisateur {u.username}", apres=c["role"])
        messages.success(request, f"Utilisateur créé : {u.username} ({c['role']}).")
        return redirect("utilisateurs")
    if "supprimer_utilisateurs" in request.POST:                 # utilisateurs cochés
        cibles = User.objects.filter(pk__in=[int(x) for x in request.POST.getlist("cochees") if x.isdigit()], is_superuser=False)
        if not cibles:
            messages.error(request, "Aucun utilisateur coché (un administrateur ne se supprime pas).")
        else:
            with transaction.atomic():
                noms = [(u.username, role(u)) for u in cibles]
                for nom, r in noms:
                    journaliser(request, "Suppression", f"utilisateur {nom}", avant=r)
                cibles.delete()
            messages.success(request, f"{len(noms)} utilisateur(s) supprimé(s) : " + ", ".join(n for n, _ in noms) + ".")
        return redirect("utilisateurs")
    liste = User.objects.prefetch_related("groups").order_by("-is_superuser", "username")
    return render(request, "compta/utilisateurs.html", {"lignes": [(u, role(u)) for u in liste], "nouveau": nouveau})


@login_required
def utilisateur(request, pk):
    administrateur(request)
    u = get_object_or_404(User, pk=pk)
    initial = {"identifiant": u.username, "prenom": u.first_name, "nom": u.last_name, "email": u.email, "role": role(u),
               "actif": u.is_active}
    form = ModifierUtilisateurForm(request.POST or None, utilisateur=u, initial=initial)
    if request.method == "POST" and form.is_valid():
        c = form.cleaned_data
        avant = f"{u.username} / {u.get_full_name()} / {u.email} / {role(u)} / {'actif' if u.is_active else 'inactif'}"
        with transaction.atomic():
            u.username, u.email, u.is_active = c["identifiant"], c["email"], c["actif"]
            u.first_name, u.last_name = c["prenom"], c["nom"]
            if c["mot_de_passe"]:
                u.set_password(c["mot_de_passe"])
            u.save()
            if c["role"] != role(u):
                donner_role(u, c["role"])
        if u == request.user and c["mot_de_passe"]:
            update_session_auth_hash(request, u)
        journaliser(request, "Modification", f"utilisateur {u.pk}", avant=avant,
                    apres=f"{u.username} / {u.get_full_name()} / {u.email} / {c['role']} / {'actif' if u.is_active else 'inactif'}"
                          + (" / mot de passe changé" if c["mot_de_passe"] else ""))
        messages.success(request, f"Utilisateur {u.username} enregistré.")
        return redirect("utilisateurs")
    return render(request, "compta/utilisateur.html", {"cible": u, "form": form})
