from django.contrib import admin
from django.contrib.auth import views as auth
from django.templatetags.static import static
from django.urls import path
from django.views.generic import RedirectView

from compta import views, vues_base, vues_parametres, vues_corrections, vues_journaux, vues_etats, vues_fiches, vues_membres, vues_rapprochement as rap

admin.site.site_header = "ComptaBB – administration"
admin.site.site_title = "ComptaBB"

urlpatterns = [
    path("", views.tableau_de_bord, name="tableau_de_bord"),
    path("ecritures/", views.ecritures, name="ecritures"),
    path("mouvement/<int:numero>/", views.mouvement, name="mouvement"),
    path("mouvement/<int:numero>/modifier/", vues_corrections.modifier, name="mouvement_modifier"),
    path("mouvement/rappel/", vues_corrections.rappeler, name="mouvement_rappel"),
    path("mouvement/nouveau/", vues_corrections.nouveau, name="mouvement_nouveau"),
    path("grand-livre/", views.grand_livre, name="grand_livre"),
    path("balance/", views.balance, name="balance"),
    path("analytique/", views.analytique, name="analytique"),
    path("controles/", views.controles, name="controles"),
    path("modifications/", views.modifications, name="modifications"),
    path("modifications/excel/", vues_journaux.historique_excel, name="historique_excel"),
    path("modifications/effacer/", vues_journaux.effacer_historique, name="effacer_historique"),
    path("journaux/", vues_journaux.journaux, name="journaux"),
    path("saisie/", views.saisie, name="saisie"),
    path("codes/", views.codes, name="codes"),
    path("fiches/", vues_fiches.liste, name="fiches"),
    path("fiches/<int:pk>/", vues_fiches.fiche, name="fiche"),
    path("fiches/<int:pk>/modifier/", vues_fiches.fiche_modifier, name="fiche_modifier"),
    path("fiches/ligne/<int:pk>/", vues_fiches.ligne, name="ligne_fiche"),
    path("rapprochement/", rap.accueil, name="rapprochement"),
    path("rapprochement/traductions/", rap.traductions, name="traductions"),
    path("rapprochement/releve/<int:pk>/ecriture/", rap.creer_ecriture, name="releve_ecriture"),
    path("rapprochement/<str:code>/", rap.accueil, name="rapprochement_journal"),
    path("rapprochement/<str:code>/import/", rap.importer, name="releve_import"),
    path("rapprochement/<str:code>/parametres/", rap.parametres, name="releve_parametres"),
    path("rapprochement/<str:code>/automatique/", rap.automatique, name="rapprochement_auto"),
    path("rapprochement/<str:code>/pointage/", rap.pointage, name="pointage"),
    path("membres/", vues_membres.liste, name="membres"),
    path("membres/modele-tiers.xlsx", vues_membres.modele_tiers, name="modele_tiers"),
    path("membres/cotisations/", vues_membres.cotisations, name="cotisations"),
    path("membres/<str:numero>/", vues_membres.fiche, name="membre"),
    path("etats/", vues_etats.etats_annuels, name="etats"),
    path("etats/export/", vues_etats.export_etats, name="export_etats"),
    path("cloture/", vues_etats.cloture, name="cloture"),
    path("cloture/archive/<int:pk>/", vues_etats.archive, name="archive"),
    path("tiers-provisoires/", vues_fiches.provisoires, name="provisoires"),
    path("connexion/", auth.LoginView.as_view(template_name="compta/connexion.html"), name="login"),
    path("deconnexion/", auth.LogoutView.as_view(), name="logout"),
    path("base/", vues_base.base, name="base"),
    path("parametres/", vues_parametres.parametres, name="parametres"),
    path("parametres/Parametres.xlsx", vues_parametres.telecharger, name="parametres_telecharger"),
    path("base/telecharger/", vues_base.telecharger, name="base_telecharger"),
    path("base/telecharger/<str:nom>", vues_base.telecharger, name="base_telecharger_fichier"),
    path("base/archive/<str:nom>", vues_base.telecharger_archive, name="base_archive"),
    path("base/export/<str:nom>", vues_base.telecharger_export, name="base_export"),
    path("admin/", admin.site.urls),
    path("favicon.ico", RedirectView.as_view(url=static("compta/favicon.ico"), permanent=True)),
]
