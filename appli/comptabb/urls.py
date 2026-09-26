from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path

from compta import views, vues_etats, vues_fiches, vues_rapprochement as rap

admin.site.site_header = "ComptaBB – administration"
admin.site.site_title = "ComptaBB"

urlpatterns = [
    path("", views.tableau_de_bord, name="tableau_de_bord"),
    path("ecritures/", views.ecritures, name="ecritures"),
    path("mouvement/<int:numero>/", views.mouvement, name="mouvement"),
    path("grand-livre/", views.grand_livre, name="grand_livre"),
    path("balance/", views.balance, name="balance"),
    path("analytique/", views.analytique, name="analytique"),
    path("controles/", views.controles, name="controles"),
    path("modifications/", views.modifications, name="modifications"),
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
    path("etats/", vues_etats.etats_annuels, name="etats"),
    path("etats/export/", vues_etats.export_etats, name="export_etats"),
    path("cloture/", vues_etats.cloture, name="cloture"),
    path("cloture/archive/<int:pk>/", vues_etats.archive, name="archive"),
    path("tiers-provisoires/", vues_fiches.provisoires, name="provisoires"),
    path("connexion/", auth.LoginView.as_view(template_name="compta/connexion.html"), name="login"),
    path("deconnexion/", auth.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
