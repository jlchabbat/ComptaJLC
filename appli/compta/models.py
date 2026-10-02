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
        return f"{self.prefixe} – {self.libelle} (axe {self.axe})" if self.libelle else f"{self.prefixe} (axe {self.axe})"

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

    @property
    def porte_axe2(self):
        """L'axe 2 (activité, événement) n'affecte que les dépenses et recettes : comptes de classe 6 ou 7."""
        return self.numero[:1] in ("6", "7")


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
    mouvement_an = models.ForeignKey("Mouvement", on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                                     verbose_name="à-nouveaux générés", help_text="Mvt d'à-nouveaux créé par la clôture.")
    resultat = models.DecimalField("résultat affecté", max_digits=14, decimal_places=2, null=True, blank=True)
    cloture_le = models.DateTimeField("clôturé le", null=True, blank=True)
    cloture_par = models.CharField("clôturé par", max_length=100, blank=True)
    archive = models.CharField(max_length=200, blank=True, help_text="Classeur figé en valeurs (dossier Exports/Archives).")

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
    valeur = models.CharField(max_length=500, blank=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "réglage"
        # administrateur et rôle Trésorier seulement : les autres utilisateurs ne touchent pas aux dossiers d'échange
        permissions = [("echanger_fichiers", "Importer et exporter des fichiers (dossiers Imports et Exports)"),
                       ("parametrer", "Modifier le paramétrage de base (administrateur)")]

    def __str__(self):
        return self.cle

    @classmethod
    def lire(cls, cle, defaut=""):
        r = cls.objects.filter(cle=cle).first()
        return r.valeur if r else defaut


class Mouvement(models.Model):
    ORIGINES = [("import", "Reprise"), ("saisie", "Saisie"), ("liaison", "Fiche bénévole"), ("correction", "Correction"),
                ("cloture", "À-nouveaux de clôture")]
    numero = models.PositiveIntegerField("Mvt", unique=True)
    date = models.DateField()
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT)
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



class Ligne(models.Model):
    mouvement = models.ForeignKey(Mouvement, on_delete=models.CASCADE, related_name="lignes")
    ordre = models.PositiveSmallIntegerField(default=0)
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT, related_name="lignes")
    libelle = models.CharField("libellé", max_length=200)
    debit = models.DecimalField("débit", max_digits=14, decimal_places=2, default=ZERO)
    credit = models.DecimalField("crédit", max_digits=14, decimal_places=2, default=ZERO)
    anal2 = models.ForeignKey(CodeAnalytique, on_delete=models.PROTECT, null=True, blank=True, limit_choices_to={"axe": 2},
                              related_name="lignes", verbose_name="axe 2", help_text="Comptes de classe 6 et 7 seulement.")
    lettrage = models.CharField(max_length=10, blank=True)
    rapprochement = models.ForeignKey("Rapprochement", on_delete=models.SET_NULL, null=True, blank=True, related_name="ecritures")

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


class DocumentFiche(models.Model):
    """Reçu, facture ou photo transmis par un bénévole avec sa fiche ; au report, il devient justificatif des mouvements."""

    fiche = models.ForeignKey("Fiche", on_delete=models.CASCADE, related_name="documents")
    ligne = models.ForeignKey("LigneFiche", on_delete=models.SET_NULL, null=True, blank=True, related_name="documents",
                              help_text="Vide = document de toute la fiche.")
    chemin = models.CharField(max_length=255, unique=True)
    nom = models.CharField("fichier d'origine", max_length=150)
    description = models.CharField(max_length=150, blank=True)
    taille = models.PositiveIntegerField(default=0)
    ajoute_le = models.DateTimeField("ajouté le", auto_now_add=True)
    ajoute_par = models.CharField("ajouté par", max_length=100, blank=True)

    class Meta:
        ordering = ["fiche", "ajoute_le", "id"]

    def __str__(self):
        return f"Fiche {self.fiche_id} · {self.nom}"


class Justificatif(models.Model):
    """Scan ou photo d'une pièce (facture, reçu, relevé…) rattaché à un mouvement.

    Soit un fichier rangé dans le dossier des données (Justificatifs/<année>/ ; chemin = chemin relatif),
    soit un lien vers le document resté dans un autre logiciel."""

    mouvement = models.ForeignKey(Mouvement, on_delete=models.CASCADE, related_name="justificatifs")
    chemin = models.CharField(max_length=255, unique=True, null=True, blank=True)
    lien = models.URLField(max_length=500, blank=True, help_text="Document consultable en ligne.")
    nom = models.CharField("fichier d'origine", max_length=150)
    description = models.CharField(max_length=150, blank=True)
    taille = models.PositiveIntegerField(default=0)
    ajoute_le = models.DateTimeField("ajouté le", auto_now_add=True)
    ajoute_par = models.CharField("ajouté par", max_length=100, blank=True)

    class Meta:
        ordering = ["mouvement", "ajoute_le", "id"]

    def __str__(self):
        return f"Mvt {self.mouvement.numero} · {self.nom}"

    @property
    def est_image(self):
        return self.nom.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "gif", "webp")


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


# ---------------------------------------------------------------- paramètres de la saisie guidée

class TypeTiers(models.Model):
    libelle = models.CharField("libellé", max_length=30, unique=True)
    prefixe = models.CharField("préfixe de compte", max_length=10)

    class Meta:
        verbose_name = "type de tiers"
        verbose_name_plural = "types de tiers"

    def __str__(self):
        return self.libelle


class MoyenPaiement(models.Model):
    libelle = models.CharField("libellé", max_length=40, unique=True)
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, null=True, blank=True,
                                help_text="Vide pour « Non réglé » (facture seule).")
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre", "libelle"]
        verbose_name = "moyen de paiement"
        verbose_name_plural = "moyens de paiement"

    def __str__(self):
        return self.libelle

    @property
    def regle(self):
        return self.journal_id is not None


class LigneSchema(models.Model):
    """Une ligne d'écriture générée par un schéma (RT, DT, RS, DS, RM, RF, VI, CB)."""

    ROLES = [("TIERS", "compte du tiers"), ("CONTREPARTIE", "compte du modèle ou saisi"), ("TRESO", "banque ou caisse"),
             ("DEST", "banque qui reçoit"), ("VIREMENT", "compte de virement interne")]
    JOURNAUX = [("PAIEMENT_OU_DEFAUT", "paiement si réglé, sinon journal du modèle"), ("DEFAUT", "journal du modèle"),
                ("PAIEMENT", "journal du paiement"), ("DESTINATION", "journal de la banque qui reçoit")]
    schema = models.CharField("schéma", max_length=4)
    ligne = models.PositiveSmallIntegerField()
    mvt = models.PositiveSmallIntegerField("Mvt", default=1)
    role = models.CharField("rôle", max_length=12, choices=ROLES)
    sens = models.CharField(max_length=1, choices=[("D", "Débit"), ("C", "Crédit")])
    si_regle = models.BooleanField("seulement si réglé", default=False)
    journal = models.CharField(max_length=20, choices=JOURNAUX)

    class Meta:
        ordering = ["schema", "ligne"]
        unique_together = [("schema", "ligne")]
        verbose_name = "ligne de schéma"
        verbose_name_plural = "schémas d'écritures"

    def __str__(self):
        return f"{self.schema}|{self.ligne}"


class ModeleOperation(models.Model):
    type = models.CharField("type d'opération", max_length=60, unique=True)
    schema = models.CharField("schéma", max_length=4)
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT, null=True, blank=True,
                               help_text="Compte de charge ou de produit proposé ; vide = à choisir à la saisie.")
    journal_defaut = models.ForeignKey(Journal, on_delete=models.PROTECT, null=True, blank=True, verbose_name="journal par défaut")
    tiers = models.ForeignKey(TypeTiers, on_delete=models.PROTECT, null=True, blank=True, help_text="Vide = sans tiers.")
    paiement_obligatoire = models.BooleanField(default=True)
    classe = models.CharField(max_length=1, blank=True, help_text="Classe attendue du compte (6 ou 7).")
    libelle_type = models.CharField("libellé type", max_length=40)
    aide = models.CharField(max_length=200, blank=True)
    ordre = models.PositiveSmallIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordre", "type"]
        verbose_name = "modèle d'opération"
        verbose_name_plural = "modèles d'opérations"

    def __str__(self):
        return self.type

    def lignes_schema(self, regle):
        return [l for l in LigneSchema.objects.filter(schema=self.schema) if regle or not l.si_regle]


# ---------------------------------------------------------------- fiches bénévoles (liaison)

FICHE_TYPES = [("activite", "Activité"), ("gestion", "Gestion")]
SENS_FICHE = [("R", "Recette"), ("D", "Dépense")]


class NatureFiche(models.Model):
    """Nature d'une ligne de fiche : donne le compte proposé et le début du libellé d'écriture."""

    type_fiche = models.CharField("fiche", max_length=10, choices=FICHE_TYPES)
    sens = models.CharField(max_length=1, choices=SENS_FICHE)
    libelle = models.CharField("libellé", max_length=60)
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT)
    libelle_ecriture = models.CharField("libellé d'écriture", max_length=40)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["type_fiche", "sens", "ordre"]
        unique_together = [("type_fiche", "sens", "libelle")]
        verbose_name = "nature (fiche bénévole)"
        verbose_name_plural = "natures (fiches bénévoles)"

    def __str__(self):
        return self.libelle


class ModeFiche(models.Model):
    """Mode de paiement d'une fiche : journal et compte de trésorerie, ou cas particulier."""

    GENRES = [("TRESO", "banque, caisse ou carte"), ("NON_PAYE", "non payé : reste dû par le membre"),
              ("AVANCE", "avance d'un membre : dette envers lui")]
    type_fiche = models.CharField("fiche", max_length=10, choices=FICHE_TYPES)
    sens = models.CharField(max_length=1, choices=SENS_FICHE + [("*", "Les deux")], default="*")
    libelle = models.CharField("libellé", max_length=40)
    genre = models.CharField(max_length=10, choices=GENRES, default="TRESO")
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT)
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT, null=True, blank=True, help_text="Vide sauf pour TRESO.")
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["type_fiche", "ordre"]
        unique_together = [("type_fiche", "sens", "libelle")]
        verbose_name = "mode de paiement (fiche bénévole)"
        verbose_name_plural = "modes de paiement (fiches bénévoles)"

    def __str__(self):
        return self.libelle


class Fiche(models.Model):
    STATUTS = [("ouverte", "Ouverte : saisie du bénévole"), ("transmise", "Transmise au trésorier"),
               ("reportee", "Reportée en comptabilité")]
    type = models.CharField(max_length=10, choices=FICHE_TYPES)
    titre = models.CharField(max_length=100)
    anal2 = models.ForeignKey(CodeAnalytique, on_delete=models.PROTECT, null=True, blank=True, limit_choices_to={"axe": 2},
                              verbose_name="code axe 2", help_text="Activité : fixé d'avance par le trésorier.")
    benevoles = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="fiches", verbose_name="bénévoles")
    statut = models.CharField(max_length=10, choices=STATUTS, default="ouverte")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cree_le"]
        permissions = [("gerer_fiche", "Compléter et reporter les fiches bénévoles")]

    def __str__(self):
        return self.titre


class TiersProvisoire(models.Model):
    """Tiers créé par un bénévole ; le trésorier lui attribue un compte."""

    nom = models.CharField(max_length=60)
    prenom = models.CharField("prénom", max_length=60, blank=True)
    remarque = models.CharField(max_length=100, blank=True, help_text="Téléphone, e-mail…")
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT, null=True, blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "prenom"]
        verbose_name = "tiers provisoire"
        verbose_name_plural = "tiers provisoires"

    def __str__(self):
        return f"{self.nom.upper()} {self.prenom.upper()}".strip() + ("" if self.compte_id else " (provisoire)")


class LigneFiche(models.Model):
    fiche = models.ForeignKey(Fiche, on_delete=models.CASCADE, related_name="lignes")
    sens = models.CharField(max_length=1, choices=SENS_FICHE)
    date = models.DateField()
    tiers = models.ForeignKey(Compte, on_delete=models.PROTECT, null=True, blank=True, related_name="lignes_fiche",
                              verbose_name="membre")
    provisoire = models.ForeignKey(TiersProvisoire, on_delete=models.PROTECT, null=True, blank=True, related_name="lignes",
                                   verbose_name="nouveau tiers")
    autre = models.CharField("autre payeur ou bénéficiaire", max_length=60, blank=True)
    personnes = models.PositiveSmallIntegerField("nombre de personnes", null=True, blank=True)
    nature = models.ForeignKey(NatureFiche, on_delete=models.PROTECT)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    mode = models.ForeignKey(ModeFiche, on_delete=models.PROTECT, null=True, blank=True, verbose_name="mode de paiement")
    justificatif = models.CharField(max_length=60, blank=True)
    remarque = models.CharField(max_length=100, blank=True)
    # colonnes du trésorier
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                               verbose_name="compte de contrepartie", help_text="Vide = compte de la nature.")
    anal2 = models.ForeignKey(CodeAnalytique, on_delete=models.PROTECT, null=True, blank=True, limit_choices_to={"axe": 2},
                              related_name="+", verbose_name="code axe 2", help_text="Gestion : choisi par le trésorier.")
    mouvement = models.ForeignKey(Mouvement, on_delete=models.PROTECT, null=True, blank=True, related_name="lignes_fiche")
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "id"]
        verbose_name = "ligne de fiche"
        verbose_name_plural = "lignes de fiches"

    def __str__(self):
        return f"{self.fiche} · {self.date:%d/%m/%Y} · {self.montant}"

    @property
    def membre(self):
        """Compte du membre : choisi directement ou attribué au tiers provisoire."""
        if self.tiers_id:
            return self.tiers
        return self.provisoire.compte if self.provisoire_id else None

    @property
    def qui(self):
        if self.tiers_id:
            return self.tiers.libelle
        if self.provisoire_id:
            return str(self.provisoire)
        return self.autre


# ---------------------------------------------------------------- rapprochement bancaire (Lot 3)

class Traduction(models.Model):
    """Libellé d'opération du relevé (hébreu) → traduction française."""

    cle = models.CharField("clé", max_length=120, unique=True, help_text="Texte hébreu sans espaces ni parenthèses.")
    hebreu = models.CharField("opération (hébreu)", max_length=120)
    traduction = models.CharField(max_length=120)

    class Meta:
        ordering = ["traduction"]
        verbose_name = "traduction (relevé)"
        verbose_name_plural = "traductions (relevés)"

    def __str__(self):
        return f"{self.hebreu} → {self.traduction}"

    @staticmethod
    def cle_de(texte):
        invisibles = dict.fromkeys(map(ord, "\u200e\u200f\u202a\u202b\u202c\u202d\u202e() <>"))
        return (texte or "").translate(invisibles).strip()

    @classmethod
    def traduire(cls, texte):
        """Traduction du libellé entier ; sinon de sa partie hébraïque seule, l'en-tête latin gardé (carte Isracard :
        « 5524 26/08/2026 הראל » → « 5524 26/08/2026 HAREL »)"""
        cle = cls.cle_de(texte)
        t = cls.objects.filter(cle__in=[cle, cle[::-1]]).first()
        if t:
            return t.traduction
        texte = texte or ""
        debut = next((i for i, c in enumerate(texte) if "\u0590" <= c <= "\u05ff"), None)
        if debut:
            cle = cls.cle_de(texte[debut:])
            t = cls.objects.filter(cle__in=[cle, cle[::-1]]).first()
            if t:
                return f"{texte[:debut].strip()} {t.traduction}".strip()
        return ""


class ParametreReleve(models.Model):
    """Paramètres du rapprochement d'un journal de trésorerie."""

    journal = models.OneToOneField(Journal, on_delete=models.CASCADE, primary_key=True)
    date_reprise = models.DateField("date de reprise en compta", null=True, blank=True,
                                    help_text="Les lignes du relevé antérieures sont couvertes par l'à-nouveau.")
    libelle = models.CharField("description du relevé", max_length=200, blank=True)

    class Meta:
        verbose_name = "paramètres de relevé"
        verbose_name_plural = "paramètres de relevés"

    def __str__(self):
        return str(self.journal)


class Rapprochement(models.Model):
    """Pointage : un groupe de lignes du relevé et d'écritures de même total."""

    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="rapprochements")
    mode = models.CharField(max_length=10, choices=[("auto", "Automatique"), ("manuel", "Manuel"), ("saisie", "Écriture créée")])
    cree_le = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        permissions = [("pointer_releve", "Importer les relevés et pointer")]

    def __str__(self):
        return f"R{self.pk}"

    @property
    def total(self):
        return sum((l.montant for l in self.releves.all()), ZERO)


class LigneReleve(models.Model):
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="releve")
    date = models.DateField()
    rang = models.PositiveSmallIntegerField(default=1, help_text="Rang dans la journée (ordre du relevé).")
    reference = models.CharField("référence", max_length=40, blank=True)
    operation = models.CharField("opération (relevé)", max_length=200, blank=True)
    montant = models.DecimalField(max_digits=14, decimal_places=2, help_text="Positif = crédit en banque (entrée).")
    solde = models.DecimalField("solde relevé", max_digits=14, decimal_places=2, null=True, blank=True)
    ouverture = models.BooleanField("solde d'ouverture", default=False)
    ecartee = models.BooleanField("écartée", default=False, help_text="Ligne volontairement laissée sans écriture ni lien.")
    rapprochement = models.ForeignKey(Rapprochement, on_delete=models.SET_NULL, null=True, blank=True, related_name="releves")
    source = models.CharField(max_length=120, blank=True)
    importe_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["journal", "date", "rang"]
        unique_together = [("journal", "date", "reference", "montant", "rang")]
        verbose_name = "ligne de relevé"
        verbose_name_plural = "lignes de relevés"

    def __str__(self):
        return f"{self.journal_id} {self.date:%d/%m/%Y} {self.montant}"

    @property
    def traduction(self):
        if self.ouverture:
            return "Solde d'ouverture"
        from .reglages import oui
        return Traduction.traduire(self.operation) or ("À traduire" if oui("traductions_releve") else self.operation)


class ImportReleve(models.Model):
    """Historique des imports de relevés bancaires (un enregistrement par fichier importé)."""
    journal = models.ForeignKey(Journal, on_delete=models.PROTECT, related_name="imports_releve")
    fichier = models.CharField(max_length=200)
    importe_le = models.DateTimeField("importé le", auto_now_add=True)
    ajoutees = models.PositiveIntegerField("lignes ajoutées", default=0)
    doublons = models.PositiveIntegerField("doublons ignorés", default=0)
    auteur = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-importe_le", "-pk"]
        verbose_name = "import de relevé"
        verbose_name_plural = "imports de relevés"

    def __str__(self):
        return f"{self.journal_id} {self.fichier}"


class AxeCompte(models.Model):
    """Classement libre des comptes (rubrique de déclaration, type, catégorie, groupe…), repris du plan comptable."""

    nom = models.CharField(max_length=40, unique=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre", "nom"]
        verbose_name = "axe de comptes"
        verbose_name_plural = "axes de comptes"

    def __str__(self):
        return self.nom


class ValeurCompte(models.Model):
    compte = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name="valeurs_axes")
    axe = models.ForeignKey(AxeCompte, on_delete=models.CASCADE, related_name="valeurs")
    valeur = models.CharField(max_length=100)

    class Meta:
        ordering = ["axe", "compte"]
        unique_together = [("compte", "axe")]
        verbose_name = "valeur d'axe de comptes"
        verbose_name_plural = "valeurs d'axes de comptes"

    def __str__(self):
        return f"{self.compte_id} · {self.axe} = {self.valeur}"


# ---------------------------------------------------------------- budget (Lot 4)

class Budget(models.Model):
    """Prévision d'un exercice, par compte, par code d'axe 1 ou par code d'axe 2."""

    exercice = models.ForeignKey(Exercice, on_delete=models.CASCADE, related_name="budgets")
    nature = models.CharField(max_length=1, choices=[("C", "Charges"), ("P", "Produits")])
    compte = models.ForeignKey(Compte, on_delete=models.PROTECT, null=True, blank=True)
    anal1 = models.ForeignKey(CodeAnalytique, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                              limit_choices_to={"axe": 1}, verbose_name="axe 1")
    anal2 = models.ForeignKey(CodeAnalytique, on_delete=models.PROTECT, null=True, blank=True, related_name="+",
                              limit_choices_to={"axe": 2}, verbose_name="axe 2")
    montant = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ["exercice", "nature", "compte", "anal1", "anal2"]
        constraints = [models.CheckConstraint(
            condition=(Q(compte__isnull=False, anal1__isnull=True, anal2__isnull=True)
                       | Q(compte__isnull=True, anal1__isnull=False, anal2__isnull=True)
                       | Q(compte__isnull=True, anal1__isnull=True, anal2__isnull=False)), name="budget_une_cible")]

    def __str__(self):
        return f"{self.exercice} {self.cible} {self.montant}"

    @property
    def cible(self):
        return self.compte or self.anal1 or self.anal2


# ---------------------------------------------------------------- suivi des membres (Lot 2)

class Membre(models.Model):
    """Fiche d'un tiers : membre, fournisseur ou tout autre type de tiers (Référentiels › Types de tiers).
    Statut, adhésion et cotisation ne concernent que les membres."""

    STATUTS = [("actif", "Actif"), ("honoraire", "Honoraire"), ("demissionnaire", "Démissionnaire")]
    compte = models.OneToOneField(Compte, on_delete=models.PROTECT, primary_key=True, related_name="membre")
    type = models.ForeignKey(TypeTiers, on_delete=models.PROTECT, null=True, blank=True, verbose_name="type de tiers")
    nom = models.CharField("nom ou raison sociale", max_length=60)
    prenom = models.CharField("prénom", max_length=60, blank=True)
    adresse = models.CharField(max_length=150, blank=True)
    code_postal = models.CharField("code postal", max_length=12, blank=True)
    ville = models.CharField(max_length=60, blank=True)
    telephone = models.CharField("téléphone", max_length=40, blank=True)
    email = models.EmailField("e-mail", blank=True)
    date_adhesion = models.DateField("date d'adhésion", null=True, blank=True)
    statut = models.CharField(max_length=15, choices=STATUTS, default="actif")
    cotisation = models.DecimalField("cotisation annuelle attendue", max_digits=10, decimal_places=2, null=True, blank=True)
    utilisateur = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="membre", verbose_name="identifiant de bénévole")

    class Meta:
        ordering = ["nom", "prenom"]
        verbose_name = "fiche tiers"
        verbose_name_plural = "fiches tiers"

    def __str__(self):
        return f"{self.nom} {self.prenom}".strip()

    @property
    def est_membre(self):
        return bool(self.type and self.type.libelle == "Membre")

    @property
    def adresse_complete(self):
        return ", ".join(x for x in (self.adresse, f"{self.code_postal} {self.ville}".strip()) if x)
