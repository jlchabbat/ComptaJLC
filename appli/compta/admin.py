from django.contrib import admin

from .models import (
    CodeAnalytique, Compte, Exercice, Journal, Ligne, LigneSchema, Modification, ModeleOperation, Mouvement,
    AxeCompte, Tiers, MoyenPaiement, ParametreReleve, Prefixe, Reglage, Traduction, TypeTiers, ValeurCompte,
)


@admin.register(CodeAnalytique)
class CodeAnalytiqueAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle")
    search_fields = ("code", "libelle")


@admin.register(Prefixe)
class PrefixeAdmin(admin.ModelAdmin):
    list_display = ("prefixe", "libelle", "code_suivant")


class ValeurCompteInline(admin.TabularInline):
    model = ValeurCompte
    extra = 1


@admin.register(Compte)
class CompteAdmin(admin.ModelAdmin):
    inlines = [ValeurCompteInline]
    list_display = ("numero", "libelle", "anal1", "lettrable", "actif")
    list_filter = ("anal1", "actif")
    search_fields = ("numero", "libelle")
    autocomplete_fields = ("anal1",)


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("code", "intitule", "type", "compte", "actif")
    search_fields = ("code", "intitule")
    autocomplete_fields = ("compte",)


@admin.register(Exercice)
class ExerciceAdmin(admin.ModelAdmin):
    list_display = ("libelle", "debut", "fin", "clos")


@admin.register(AxeCompte)
class AxeCompteAdmin(admin.ModelAdmin):
    list_display = ("nom", "ordre")


@admin.register(Reglage)
class ReglageAdmin(admin.ModelAdmin):
    list_display = ("cle", "valeur", "description")


class LigneInline(admin.TabularInline):
    model = Ligne
    extra = 0
    autocomplete_fields = ("compte",)


@admin.register(Mouvement)
class MouvementAdmin(admin.ModelAdmin):
    list_display = ("numero", "date", "journal", "origine")
    list_filter = ("journal", "origine")
    search_fields = ("numero", "lignes__libelle")
    inlines = [LigneInline]

    def has_change_permission(self, request, obj=None):
        # les écritures ne se modifient pas ici : saisie guidée et corrections tracées (lot suivant)
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


@admin.register(Modification)
class ModificationAdmin(admin.ModelAdmin):
    list_display = ("date", "auteur", "lot", "action", "objet")
    list_filter = ("lot", "action")

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TypeTiers)
class TypeTiersAdmin(admin.ModelAdmin):
    list_display = ("libelle", "prefixe")


@admin.register(MoyenPaiement)
class MoyenPaiementAdmin(admin.ModelAdmin):
    list_display = ("libelle", "journal", "ordre")
    autocomplete_fields = ("journal",)


@admin.register(LigneSchema)
class LigneSchemaAdmin(admin.ModelAdmin):
    list_display = ("schema", "ligne", "mvt", "role", "sens", "si_regle", "journal")
    list_filter = ("schema",)


@admin.register(ModeleOperation)
class ModeleOperationAdmin(admin.ModelAdmin):
    list_display = ("type", "schema", "compte", "journal_defaut", "tiers", "paiement_obligatoire", "classe", "ordre", "actif")
    search_fields = ("type", "libelle_type")
    autocomplete_fields = ("compte", "journal_defaut")


@admin.register(Traduction)
class TraductionAdmin(admin.ModelAdmin):
    list_display = ("hebreu", "traduction")
    search_fields = ("hebreu", "traduction")
    fields = ("hebreu", "traduction")

    def save_model(self, request, obj, form, change):
        obj.cle = Traduction.cle_de(obj.hebreu)[:120]
        super().save_model(request, obj, form, change)


@admin.register(ParametreReleve)
class ParametreReleveAdmin(admin.ModelAdmin):
    list_display = ("journal", "date_reprise", "libelle")


@admin.register(Tiers)
class TiersAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "compte", "type", "telephone", "email")
    list_filter = ("type",)
    search_fields = ("nom", "prenom", "compte__numero", "email")
