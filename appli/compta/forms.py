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
    tiers = forms.ModelChoiceField(Compte.objects.none(), required=False, label="Tiers (membre ou fournisseur)")
    montant = forms.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0, label="Montant")
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

    def __init__(self, *a, axe1=False, **k):
        super().__init__(*a, **k)
        if not axe1:                                     # axe 1 : paramétrage de base (administrateur)
            self.fields["prefixe"].queryset = Prefixe.objects.filter(axe=2)
            self.fields["prefixe"].help_text = "Axe 2 seulement ; les codes d'axe 1 sont créés par l'administrateur."
        cherchable(self)


class MembreForm(forms.Form):
    """Nouveau tiers : membre, fournisseur… (le compte est proposé d'après le type et le nom)."""

    type = forms.ModelChoiceField(TypeTiers.objects.all(), label="Type de tiers", empty_label=None)
    nom = forms.CharField(max_length=60, label="Nom ou raison sociale")
    prenom = forms.CharField(max_length=60, required=False, label="Prénom")
    nouveau_tel = forms.CharField(max_length=40, required=False, label="Téléphone (facultatif)")
    nouveau_email = forms.EmailField(required=False, label="E-mail (facultatif)")
    adresse = forms.CharField(max_length=150, required=False)
    code_postal = forms.CharField(max_length=12, required=False, label="Code postal")
    ville = forms.CharField(max_length=60, required=False)
    telephone = forms.CharField(max_length=40, required=False, label="Téléphone")
    email = forms.EmailField(required=False, label="E-mail")


class StatutForm(forms.Form):
    code = forms.ModelChoiceField(CodeAnalytique.objects.filter(axe=2), label="Code")
    statut = forms.TypedChoiceField(choices=CodeAnalytique.STATUTS, coerce=int, label="Nouveau statut")
    confirmation = forms.BooleanField(required=False, label="Je confirme : ce code est déjà utilisé dans des écritures")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["code"].queryset = CodeAnalytique.objects.filter(axe=2).order_by("code")
        cherchable(self)


# ---------------------------------------------------------------- fiches bénévoles

from django.contrib.auth.models import User  # noqa: E402

from .models import Fiche, LigneFiche, Membre, ModeFiche, NatureFiche, TiersProvisoire  # noqa: E402


def identifiant_libre(v, sauf=None):
    """Identifiant de connexion : lettres, chiffres et @ . + - _ (une adresse e-mail convient), unique sans tenir compte des majuscules."""
    from django.contrib.auth.validators import UnicodeUsernameValidator
    v = v.strip()
    UnicodeUsernameValidator()(v)
    autres = User.objects.exclude(pk=sauf.pk) if sauf else User.objects.all()
    if autres.filter(Q(username__iexact=v) | Q(email__iexact=v)).exists():
        raise forms.ValidationError("Cet identifiant est déjà utilisé.")
    return v


def comptes_tiers():
    prefixes = Q()
    for t in TypeTiers.objects.all():
        prefixes |= Q(numero__startswith=t.prefixe)
    return Compte.objects.filter(prefixes, actif=True).order_by("libelle") if prefixes else Compte.objects.none()


class ChoixBenevoles(forms.ModelMultipleChoiceField):
    def label_from_instance(self, u):
        return u.get_full_name() or u.username


class FicheForm(forms.ModelForm):
    """Fiche : à la création, le code axe 2 se choisit dans la liste ou se crée (préfixe + libellé)."""

    nouveau_prefixe = forms.ModelChoiceField(Prefixe.objects.none(), required=False, label="Ou nouveau code : préfixe")
    nouveau_libelle = forms.CharField(max_length=100, required=False, label="Nouveau code : libellé",
                                      help_text="Le code est numéroté automatiquement (ex. MAN.008).")
    benevoles = ChoixBenevoles(User.objects.none(), required=False, widget=forms.CheckboxSelectMultiple(attrs={"class": "radios"}),
                                label="Bénévoles")

    class Meta:
        model = Fiche
        fields = ["type", "titre", "anal2", "benevoles"]

    field_order = ["type", "titre", "anal2", "nouveau_prefixe", "nouveau_libelle", "benevoles"]

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["anal2"].queryset = CodeAnalytique.objects.filter(axe=2).exclude(statut=2).order_by("code")
        self.fields["benevoles"].queryset = User.objects.filter(groups__name="Bénévole", is_active=True).order_by("username")
        if self.instance.pk:
            del self.fields["type"], self.fields["nouveau_prefixe"], self.fields["nouveau_libelle"]
        else:
            prefixes = Prefixe.objects.filter(axe=2)
            self.fields["nouveau_prefixe"].queryset = prefixes
            if prefixes.count() == 1:
                self.fields["nouveau_prefixe"].initial = prefixes.get()
        cherchable(self)

    def clean(self):
        c = super().clean()
        lib = (c.get("nouveau_libelle") or "").strip().upper()
        c["nouveau_libelle"] = lib
        if lib:
            if c.get("anal2"):
                self.add_error("nouveau_libelle", "Choisissez un code existant OU créez-en un, pas les deux.")
            elif not c.get("nouveau_prefixe"):
                self.add_error("nouveau_prefixe", "Préfixe obligatoire pour créer le code.")
            elif CodeAnalytique.objects.filter(axe=2, libelle=lib).exists():
                self.add_error("nouveau_libelle", "Ce libellé existe déjà sur l'axe 2 : choisissez-le dans la liste.")
        return c

    def save(self, commit=True):
        lib = self.cleaned_data.get("nouveau_libelle")
        if lib:
            self.instance.anal2 = CodeAnalytique.objects.create(code=self.cleaned_data["nouveau_prefixe"].code_suivant(), axe=2,
                                                                libelle=lib, statut=1)
        return super().save(commit)


class BenevoleForm(forms.Form):
    """Un bénévole est toujours un membre : on le choisit dans les fiches tiers."""

    membre = forms.ModelChoiceField(Membre.objects.none(), label="Membre",
                                    help_text="Tapez le nom. Absent ? Créez d'abord sa fiche (Tiers, type Membre).")
    identifiant = forms.CharField(max_length=150, help_text="Pour se connecter : un nom sans espace ou une adresse e-mail.")
    mot_de_passe = forms.CharField(min_length=8, widget=forms.PasswordInput(render_value=True), label="Mot de passe",
                                   help_text="8 caractères au moins ; à transmettre au bénévole.")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["membre"].queryset = (Membre.objects.filter(type__libelle="Membre", utilisateur__isnull=True)
                                          .exclude(statut="demissionnaire").order_by("nom", "prenom"))
        cherchable(self)

    clean_identifiant = lambda self: identifiant_libre(self.cleaned_data["identifiant"])  # noqa: E731


class LigneFicheForm(forms.ModelForm):
    """Ligne saisie par le bénévole ; le trésorier voit en plus ses colonnes (mode en gestion, compte, axe 2)."""

    sens = forms.ChoiceField(choices=[("R", "Recette"), ("D", "Dépense")], widget=forms.RadioSelect(attrs={"class": "radios"}))
    qui = forms.ChoiceField(required=False, label="Tiers connu",
                            help_text="Membre ou tiers répertorié : tapez le nom.")
    nouveau_nom = forms.CharField(max_length=60, required=False, label="Nouveau tiers : nom",
                                  help_text="Absent de la liste ? Le trésorier lui attribuera un compte.")
    nouveau_prenom = forms.CharField(max_length=60, required=False, label="Prénom")

    class Meta:
        model = LigneFiche
        fields = ["sens", "date", "personnes", "nature", "montant", "mode", "justificatif", "remarque", "anal2"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    field_order = ["sens", "date", "qui", "nouveau_nom", "nouveau_prenom", "nouveau_tel", "nouveau_email", "personnes", "nature", "montant", "mode",
                   "justificatif", "remarque", "anal2"]

    def __init__(self, *a, fiche, tresorier, **k):
        super().__init__(*a, **k)
        self.fiche = fiche
        t = fiche.type
        f = self.fields
        f["nature"].queryset = NatureFiche.objects.filter(type_fiche=t)
        f["mode"].queryset = ModeFiche.objects.filter(type_fiche=t)
        f["montant"].min_value = 0
        choix = [("", "—")]
        choix += [(f"c:{c.numero}", f"{c.libelle} – {c.numero}") for c in comptes_tiers()]
        choix += [(f"p:{p.pk}", f"{p} – nouveau tiers") for p in TiersProvisoire.objects.filter(compte__isnull=True)]
        f["qui"].choices = choix
        if self.instance.pk:
            i = self.instance
            f["qui"].initial = f"c:{i.tiers_id}" if i.tiers_id else (f"p:{i.provisoire_id}" if i.provisoire_id else "")
        if t == "gestion":
            for n in ("personnes", "justificatif"):
                del f[n]
            if not tresorier:
                del f["mode"]
        if tresorier:
            f["anal2"].queryset = CodeAnalytique.objects.filter(axe=2).exclude(statut=2).order_by("code")
            if t == "activite":
                del f["anal2"]
        else:
            del f["anal2"]
        if fiche.type == "gestion":
            f["sens"].choices = [("R", "Reçu"), ("D", "Versé")]
        cherchable(self)
        f["qui"].widget.attrs.update(CHERCHABLE)

    def clean(self):
        c = super().clean()
        qui, nom = c.get("qui"), (c.get("nouveau_nom") or "").strip()
        if qui and nom:
            self.add_error("nouveau_nom", "Tiers connu OU nouveau tiers, pas les deux.")
        return c

    def save(self, utilisateur):
        l = super().save(commit=False)
        l.fiche = self.fiche
        qui, nom = self.cleaned_data.get("qui"), (self.cleaned_data.get("nouveau_nom") or "").strip()
        l.tiers = l.provisoire = None
        if qui.startswith("c:"):
            l.tiers = Compte.objects.get(numero=qui[2:])
        elif qui.startswith("p:"):
            l.provisoire = TiersProvisoire.objects.get(pk=qui[2:])
        elif nom:
            l.provisoire = TiersProvisoire.objects.create(nom=nom, prenom=(self.cleaned_data.get("nouveau_prenom") or "").strip(),
                                                          remarque=" · ".join(x for x in (self.cleaned_data.get("nouveau_tel"),
                                                                                         self.cleaned_data.get("nouveau_email")) if x)[:100],
                                                          cree_par=utilisateur)
        if not l.pk:
            l.cree_par = utilisateur
        l.save()
        return l


class AttribuerForm(forms.Form):
    compte = forms.ModelChoiceField(Compte.objects.none(), required=False, label="Compte existant",
                                    help_text="Vide : un nouveau compte est créé, du type choisi ci-dessous.")
    type = forms.ModelChoiceField(TypeTiers.objects.all(), label="Type (nouveau compte)", empty_label=None)

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["compte"].queryset = comptes_tiers()
        self.fields["type"].initial = TypeTiers.objects.filter(libelle="Membre").first()
        cherchable(self)


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
    anal2 = forms.ModelChoiceField(CodeAnalytique.objects.none(), required=False, label="Axe 2")

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.fields["compte"].queryset = Compte.objects.filter(actif=True)
        self.fields["anal2"].queryset = CodeAnalytique.objects.filter(axe=2)
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
        if not c.get("anal2") and c.get("compte") and c["compte"].porte_axe2:       # axe 2 facultatif ; un seul axe : code d'office
            from .reglages import code_axe2_defaut
            defaut = code_axe2_defaut()
            if defaut:
                c["anal2"] = CodeAnalytique.objects.get(code=defaut)
        return c


LignesMouvementFormSet = forms.formset_factory(LigneMouvementForm, extra=2, can_delete=True)
