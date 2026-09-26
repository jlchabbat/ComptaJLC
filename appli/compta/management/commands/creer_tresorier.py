"""Crée un compte trésorier (tous les droits) : python manage.py creer_tresorier"""

import getpass

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Crée un utilisateur du rôle Trésorier."

    def handle(self, **options):
        nom = input("Identifiant du trésorier : ").strip()
        if not nom or User.objects.filter(username=nom).exists():
            raise CommandError("Identifiant vide ou déjà utilisé.")
        mdp = getpass.getpass("Mot de passe (12 caractères au moins) : ")
        if len(mdp) < 12 or mdp != getpass.getpass("Encore une fois : "):
            raise CommandError("Mot de passe trop court ou différent.")
        u = User.objects.create_superuser(nom, "", mdp)
        u.groups.add(Group.objects.get(name="Trésorier"))
        self.stdout.write(self.style.SUCCESS(f"Trésorier « {nom} » créé."))
