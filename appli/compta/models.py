"""Modèle comptable de ComptaBB.

Un mouvement (Mvt) = une opération équilibrée : une date, un journal, une
pièce, et des lignes qui portent chacune un débit OU un crédit, un compte et
un code analytique d'axe 2. L'axe 1 découle du compte (plan comptable).
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum

ZERO = Decimal("0.00")


class CodeAnalytique(models.Model):
    """Axe 1 (nature) ou axe 2 (événement, projet)."""

    STATUTS = [(0, "Non affecté"), (1, "En cours"), (2, "Terminé")]
    code = models.CharField(max_length=20, primary_key=True)
    axe = models.PositiveSmallIntegerField(choices=[(1, "Axe 1"), (2, "Axe 2")])
    libelle = models.CharField("libellé", max_length=100, blank=True)
    statut = models.PositiveSmallIntegerField(choices=STATUTS, default=1)

    class Meta:
        ordering = ["axe", "code"]
        verbose_name = "code analytique"
        verbose_name_plural = "codes analytiques"

    def __str__(self):
        return f"{self.code} – {self.libelle}" if self.libelle else self.code


class Prefixe(models.Model):
    prefixe = models.CharField("préfixe", max_length=10, primary_key=True)
    axe = models.PositiveSmallIntegerField(choices=[(1, "Axe 1"), (2, "Axe 2")])
    libelle = models.CharField("libellé", max_length=60, blank=True)

    class Meta:
        ordering = ["axe", "prefixe"]
        verbose_name = "préfixe"

    def __str__(self):
        return self.prefixe

    def code_suivant(self):
        """Plus grand numéro existant + 1 ; 1 chiffre pour l'axe 1, 3 pour l'axe 2."""
        suffixes = [c[len(self.prefixe):] for c in CodeAnalytique.objects.filter(code__startswith=self.prefixe)
                    .values_list("code", flat=True)]
        nums = [s for s in suffixes if s.isdigit()]
        largeur = max([3 if self.axe == 2 else 1] + [len(s) for s in nums])
        return self.prefixe + str(max([int(s) for s in nums], default=0) + 1).zfill(largeur)


class Compte(models.Model):
    numero = models.CharField("compte", max_length=20, primary_key=True)
    libelle = models.CharField("libellé", max_length=100)
    anal1 = models.ForeignKey(CodeAnalytique, on_delete=models.PROTECT, null=True, blank=True, limit_choices_to={"axe": 1},
                              related_name="comptes", verbose_name="axe 1")
    lettrable = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["numero"]

    def __str__(self):
        return f"{self.numero} – {self.libelle}"

    @property
    def classe(self):
        return self.numero[:1]


class Journal(models.Model):
    code = models.CharField(max_length=10, primary_key=True)
    intitule = models.CharField("intitulé", max_length=60)
    type = models.CharField(max_length=10, blank=True)
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT, null=True, blank=True,
                               help_text="Compte de trésorerie des journaux de banque et de caisse.")
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "journaux"

    def __str__(self):
        return f"{self.code} – {self.intitule}"


class Exercice(models.Model):
    libelle = models.CharField("libellé", max_length=40)
    debut = models.DateField("début")
    fin = models.DateField()
    clos = models.BooleanField(default=False, help_text="Aucune écriture nouvelle dans un exercice clos (RG-04).")

    class Meta:
        ordering = ["debut"]

    def __str__(self):
        return self.libelle

    @classmethod
    def ouvert(cls):
        return cls.objects.filter(clos=False).order_by("debut").first()

    @classmethod
    def date_close(cls, date):
        return cls.objects.filter(clos=True, debut__lte=date, fin__gte=date).exists()


class Reglage(models.Model):
    """Hypothèses nommées (RG-06) : compte de virement interne, compte d'attente…"""

    cle = models.CharField("clé", max_length=40, primary_key=True)
    valeur = models.CharField(max_length=200)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "réglage"

    def __str__(self):
        return self.cle

    @classmethod
    def lire(cls, cle, defaut=""):
        r = cls.objects.filter(cle=cle).first()
        return r.valeur if r else defaut


class Mouvement(models.Model):
    ORIGINES = [("import", "Reprise"), ("saisie", "Saisie"), ("liaison", "Fiche bénévole"), ("correction", "Correction")]
    numero = models.PositiveIntegerField("Mvt", unique=True)
    date = models.DateField()
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT)
    piece = models.PositiveIntegerField("pièce")
    origine = models.CharField(max_length=12, choices=ORIGINES, default="saisie")
    commentaire = models.TextField(blank=True, help_text="Origine et motif d'une écriture ajoutée ou corrigée (RG-05).")
    cree_le = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-date", "-numero"]

    def __str__(self):
        return f"Mvt {self.numero}"

    @property
    def total_debit(self):
        return sum((l.debit for l in self.lignes.all()), ZERO)

    @property
    def total_credit(self):
        return sum((l.credit for l in self.lignes.all()), ZERO)

    @classmethod
    def prochain_numero(cls):
        return (cls.objects.aggregate(m=models.Max("numero"))["m"] or 0) + 1

    @classmethod
    def prochaine_piece(cls):
        return (cls.objects.aggregate(m=models.Max("piece"))["m"] or 0) + 1


class Ligne(models.Model):
    mouvement = models.ForeignKey(Mouvement, on_delete=models.CASCADE, related_name="lignes")
    ordre = models.PositiveSmallIntegerField(default=0)
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT, related_name="lignes")
    libelle = models.CharField("libellé", max_length=200)
    debit = models.DecimalField("débit", max_digits=14, decimal_places=2, default=ZERO)
    credit = models.DecimalField("crédit", max_digits=14, decimal_places=2, default=ZERO)
    anal2 = models.ForeignKey(CodeAnalytique, on_delete=models.PROTECT, limit_choices_to={"axe": 2}, related_name="lignes",
                              verbose_name="axe 2")
    lettrage = models.CharField(max_length=10, blank=True)

    class Meta:
        ordering = ["mouvement", "ordre"]
        constraints = [
            models.CheckConstraint(condition=(Q(debit__gt=0) & Q(credit=0)) | (Q(credit__gt=0) & Q(debit=0)),
                                   name="debit_ou_credit"),
        ]

    def __str__(self):
        return f"{self.mouvement} · {self.compte_id} · {self.debit or -self.credit}"

    def clean(self):
        if (self.debit > 0) == (self.credit > 0):
            raise ValidationError("Une ligne porte soit un débit, soit un crédit (RG-03).")

    @property
    def montant(self):
        return self.debit - self.credit


class Modification(models.Model):
    """Journal des modifications (cahier des charges §9)."""

    date = models.DateTimeField(auto_now_add=True)
    auteur = models.CharField(max_length=100)
    lot = models.CharField(max_length=20, blank=True)
    action = models.CharField(max_length=40)
    objet = models.CharField(max_length=200)
    avant = models.CharField(max_length=300, blank=True)
    apres = models.CharField("après", max_length=300, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "modification"

    def __str__(self):
        return f"{self.date:%d/%m/%Y} {self.action} {self.objet}"


def arrondi(v):
    """Montant au centime (SQLite renvoie des sommes décimales non arrondies)."""
    return (v or ZERO).quantize(Decimal("0.01"))


def soldes(lignes):
    """Débit, crédit et solde (débit − crédit) d'un ensemble de lignes."""
    t = lignes.aggregate(d=Sum("debit"), c=Sum("credit"))
    d, c = arrondi(t["d"]), arrondi(t["c"])
    return d, c, d - c
