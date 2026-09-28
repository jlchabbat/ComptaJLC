from django.apps import AppConfig
from django.db.models.signals import post_migrate

# Paramétrage de base : réservé à l'administrateur (Référentiels, Paramètres Excel, codes axe 1, relevés, utilisateurs)
PARAMETRAGE = ["journal", "prefixe", "typetiers", "moyenpaiement", "ligneschema", "modeleoperation", "naturefiche", "modefiche",
               "reglage", "parametrereleve"]

# Rôles (cahier des charges §1) : droits Django attribués à chaque groupe, du plus large au plus restreint
ROLES = {
    "Administrateur": "tout",      # au-dessus du trésorier : paramétrage de base, utilisateurs, base de données
    "Trésorier": "tenue",          # tenue quotidienne des comptes : ni paramétrage, ni imports / exports, ni base de données
    "Bureau": "consultation",
    # fiches bénévoles : le bénévole ne voit que les fiches qui lui sont confiées
    "Bénévole": ["view_fiche", "add_lignefiche", "change_lignefiche", "delete_lignefiche", "view_tiersprovisoire",
                 "add_tiersprovisoire"],
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
        elif portee == "consultation":
            groupe.permissions.set(perms.filter(codename__startswith="view_"))
        elif isinstance(portee, list):
            groupe.permissions.set(perms.filter(codename__in=portee))


class ComptaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "compta"
    verbose_name = "Comptabilité"

    def ready(self):
        post_migrate.connect(creer_roles, sender=self)
