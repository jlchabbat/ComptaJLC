from django import forms
from django.db.models import Q

from .models import CodeAnalytique, Compte, ModeleOperation, MoyenPaiement, Prefixe, TypeTiers


CHERCHABLE = {"data-cherchable": "Code ou libellé…"}


def cherchable(form):
    """Toutes les listes du formulaire deviennent cherchables par code ou libellé (static/compta/liste.js)."""
    for f in form.fields.values():
        if isinstance(f, forms.ModelChoiceField):
            f.widget.attrs.update(CHERCHABLE)


class SaisieForm(forms.Form):
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    modele = forms.ModelChoiceField(ModeleOperation.objects.none(), required=False, label="Type d'opération")
    tiers = forms.ModelChoiceField(Compte.objects.none(), required=False, label="Tiers (membre ou fournisseur)")
    montant = forms.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0, label="Montant (₪)")
    paiement = forms.ModelChoiceField(MoyenPaiement.objects.none(), required=False, label="Moyen de paiement")
    vers = forms.ModelChoiceField(MoyenPaiement.objects.none(), required=False, label="Vers (virement interne)")
    anal2 = forms.ModelChoiceField(CodeAnalytique.objects.none(), required=False, label="Événement / projet (axe 2)")
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
        self.fields["anal2"].queryset = CodeAnalytique.objects.filter(axe=2).order_by("code")
        self.fields["compte"].queryset = Compte.objects.filter(Q(numero__startswith="6") | Q(numero__startswith="7"), actif=True)
        cherchable(self)


class CodeForm(forms.Form):
    prefixe = forms.ModelChoiceField(Prefixe.objects.all(), label="Préfixe")
    libelle = forms.CharField(max_length=100, label="Libellé")
    statut = forms.TypedChoiceField(choices=CodeAnalytique.STATUTS, coerce=int, initial=1, label="Statut (axe 2)")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        cherchable(self)


class MembreForm(forms.Form):
    nom = forms.CharField(max_length=60)
    prenom = forms.CharField(max_length=60, required=False, label="Prénom")


class StatutForm(forms.Form):
    code = forms.ModelChoiceField(CodeAnalytique.objects.filter(axe=2), label="Code")
    statut = forms.TypedChoiceField(choices=CodeAnalytique.STATUTS, coerce=int, label="Nouveau statut")
    confirmation = forms.BooleanField(required=False, label="Je confirme : ce code est déjà utilisé dans des écritures")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["code"].queryset = CodeAnalytique.objects.filter(axe=2).order_by("code")
        cherchable(self)
