from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path

from compta import views, vues_fiches

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
    path("tiers-provisoires/", vues_fiches.provisoires, name="provisoires"),
    path("connexion/", auth.LoginView.as_view(template_name="compta/connexion.html"), name="login"),
    path("deconnexion/", auth.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
