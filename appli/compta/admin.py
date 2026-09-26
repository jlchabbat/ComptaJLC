from django.contrib import admin

from .models import CodeAnalytique, Compte, Exercice, Journal, Ligne, Modification, Mouvement, Prefixe, Reglage


@admin.register(CodeAnalytique)
class CodeAnalytiqueAdmin(admin.ModelAdmin):
    list_display = ("code", "axe", "libelle", "statut")
    list_filter = ("axe", "statut")
    search_fields = ("code", "libelle")


@admin.register(Prefixe)
class PrefixeAdmin(admin.ModelAdmin):
    list_display = ("prefixe", "axe", "libelle", "code_suivant")


@admin.register(Compte)
class CompteAdmin(admin.ModelAdmin):
    list_display = ("numero", "libelle", "anal1", "lettrable", "actif")
    list_filter = ("anal1", "actif")
    search_fields = ("numero", "libelle")


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    list_display = ("code", "intitule", "type", "compte", "actif")


@admin.register(Exercice)
class ExerciceAdmin(admin.ModelAdmin):
    list_display = ("libelle", "debut", "fin", "clos")


@admin.register(Reglage)
class ReglageAdmin(admin.ModelAdmin):
    list_display = ("cle", "valeur", "description")


class LigneInline(admin.TabularInline):
    model = Ligne
    extra = 0
    autocomplete_fields = ("compte",)


@admin.register(Mouvement)
class MouvementAdmin(admin.ModelAdmin):
    list_display = ("numero", "date", "journal", "piece", "origine")
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
