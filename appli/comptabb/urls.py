from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path

from compta import views

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
    path("connexion/", auth.LoginView.as_view(template_name="compta/connexion.html"), name="login"),
    path("deconnexion/", auth.LogoutView.as_view(), name="logout"),
    path("admin/", admin.site.urls),
]
