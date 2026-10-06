from django.apps import AppConfig
from django.db.models.signals import post_migrate

# Paramétrage de base : réservé à l'administrateur (Référentiels, Paramètres Excel, codes axe 1, relevés, utilisateurs)
PARAMETRAGE = ["journal", "prefixe", "typetiers", "moyenpaiement", "ligneschema", "modeleoperation",
               "reglage", "parametrereleve"]

# Deux modes de travail : Administration et Gestion (droits Django attribués à chaque groupe)
ROLES = {
    "Administration": "tout",      # au-dessus de la gestion : paramétrage de base, utilisateurs, base de données
    "Gestion": "tenue",          # tenue quotidienne des comptes : ni paramétrage, ni imports / exports, ni base de données
}


def creer_roles(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    perms = Permission.objects.filter(content_type__app_label="compta")
    for nom, portee in ROLES.items():
        groupe, _ = Group.objects.get_or_create(name=nom)
        if portee == "tout":
            groupe.permissions.set(perms)
        elif portee == "tenue":
            # administrateur seulement : paramétrage de base, et imports / exports de fichiers (reprise, réinstallation)
            reserves = [f"{a}_{m}" for m in PARAMETRAGE for a in ("add", "change", "delete")] + ["parametrer", "echanger_fichiers"]
            groupe.permissions.set(perms.exclude(codename__in=reserves))
    for ancien in Group.objects.filter(name__in=("Consultation", "Bénévole"), user__isnull=True):
        ancien.delete()                                  # anciens rôles sans utilisateur : supprimés


class ComptaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "compta"
    verbose_name = "Comptabilité"

    def ready(self):
        post_migrate.connect(creer_roles, sender=self)
