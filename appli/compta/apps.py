from django.apps import AppConfig
from django.db.models.signals import post_migrate

# Rôles (cahier des charges §1) : droits Django attribués à chaque groupe
ROLES = {
    "Trésorier": "tout",
    "Bureau": "consultation",
    "Vérificateur": "consultation",
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
