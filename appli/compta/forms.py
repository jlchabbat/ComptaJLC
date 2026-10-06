from django import forms
from django.db.models import Q

from .models import CodeAnalytique, Compte, Journal, ModeleOperation, MoyenPaiement, Prefixe, TypeTiers


CHERCHABLE = {"data-cherchable": "Code ou libellé…"}


def cherchable(form):
    """Toutes les listes du formulaire deviennent cherchables par code ou libellé (static/compta/liste.js)."""
    for f in form.fields.values():
        if isinstance(f, forms.ModelChoiceField):
            f.widget.attrs.update(CHERCHABLE)


class SaisieForm(forms.Form):
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    modele = forms.ModelChoiceField(ModeleOperation.objects.none(), required=False, label="Type d'opération")
    tiers = forms.ModelChoiceField(Compte.objects.none(), required=False, label="Tiers (client ou fournisseur)")
    montant = forms.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0, label="Montant")
    paiement = forms.ModelChoiceField(MoyenPaiement.objects.none(), required=False, label="Moyen de paiement")
    vers = forms.ModelChoiceField(MoyenPaiement.objects.none(), required=False, label="Vers (virement interne)")
    compte = forms.ModelChoiceField(Compte.objects.none(), required=False, label="Compte (si différent du modèle)")
    remboursement = forms.BooleanField(required=False, label="Remboursement (écritures inversées)")
    libelle = forms.CharField(required=False, max_length=60, label="Libellé (facultatif)")
    forcer = forms.BooleanField(required=False, label="Enregistrer quand même : ce n'est pas un doublon")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["modele"].queryset = ModeleOperation.objects.filter(actif=True)
        prefixes = Q()
        for t in TypeTiers.objects.all():
            prefixes |= Q(numero__startswith=t.prefixe)
        self.fields["tiers"].queryset = Compte.objects.filter(prefixes, actif=True).order_by("libelle") if prefixes else Compte.objects.none()
        self.fields["paiement"].queryset = MoyenPaiement.objects.all()
        self.fields["vers"].queryset = MoyenPaiement.objects.filter(journal__isnull=False)
        self.fields["compte"].queryset = Compte.objects.filter(Q(numero__startswith="6") | Q(numero__startswith="7"), actif=True)
        cherchable(self)


class CodeForm(forms.Form):
    prefixe = forms.ModelChoiceField(Prefixe.objects.all(), label="1. Préfixe")
    libelle = forms.CharField(max_length=100, label="2. Libellé")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        cherchable(self)


class TiersForm(forms.Form):
    """Nouveau tiers : client, fournisseur… (le compte est proposé d'après le type et le nom)."""

    type = forms.ModelChoiceField(TypeTiers.objects.all(), label="Type de tiers", empty_label=None)
    nom = forms.CharField(max_length=60, label="Nom (ou raison sociale), prénom", widget=forms.TextInput(attrs={"placeholder": "Nom"}))
    prenom = forms.CharField(max_length=60, required=False, label="Prénom",
                             widget=forms.TextInput(attrs={"data-avec": "nom", "placeholder": "Prénom"}))
    telephone = forms.CharField(max_length=40, required=False, label="Téléphone, e-mail", widget=forms.TextInput(attrs={"placeholder": "Téléphone"}))
    email = forms.EmailField(required=False, label="E-mail", widget=forms.EmailInput(attrs={"data-avec": "telephone", "placeholder": "E-mail"}))
    adresse = forms.CharField(max_length=150, required=False)
    code_postal = forms.CharField(max_length=12, required=False, label="Code postal, ville", widget=forms.TextInput(attrs={"placeholder": "Code postal"}))
    ville = forms.CharField(max_length=60, required=False, widget=forms.TextInput(attrs={"data-avec": "code_postal", "placeholder": "Ville"}))


# ---------------------------------------------------------------- identifiants des utilisateurs

from django.contrib.auth.models import User  # noqa: E402



def identifiant_libre(v, sauf=None):
    """Identifiant de connexion : lettres, chiffres et @ . + - _ (une adresse e-mail convient), unique sans tenir compte des majuscules."""
    from django.contrib.auth.validators import UnicodeUsernameValidator
    v = v.strip()
    UnicodeUsernameValidator()(v)
    autres = User.objects.exclude(pk=sauf.pk) if sauf else User.objects.all()
    if autres.filter(Q(username__iexact=v) | Q(email__iexact=v)).exists():
        raise forms.ValidationError("Cet identifiant est déjà utilisé.")
    return v


# ---------------------------------------------------------------- corrections d'écritures

class EnteteMouvementForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    journal = forms.ModelChoiceField(Journal.objects.filter(actif=True))
    motif = forms.CharField(max_length=150, required=False, label="Motif (facultatif)")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        cherchable(self)


class LigneMouvementForm(forms.Form):
    id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    compte = forms.ModelChoiceField(Compte.objects.none(), required=False)
    libelle = forms.CharField(max_length=200, required=False, label="Libellé")
    debit = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False, label="Débit")
    credit = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, required=False, label="Crédit")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["compte"].queryset = Compte.objects.filter(actif=True)
        cherchable(self)
        self.fields["libelle"].widget.attrs["size"] = 30
        for n in ("debit", "credit"):
            self.fields[n].widget.attrs.update({"class": "montant", "step": "0.01"})

    def vide(self):
        c = self.cleaned_data
        return not (c.get("compte") or c.get("debit") or c.get("credit") or (c.get("libelle") or "").strip())

    def clean(self):
        c = super().clean()
        if c.get("DELETE") or self.vide():
            return c
        if not c.get("compte"):
            self.add_error("compte", "Choisir le compte.")
        return c


LignesMouvementFormSet = forms.formset_factory(LigneMouvementForm, extra=2, can_delete=True)
