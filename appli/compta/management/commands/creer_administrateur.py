"""Crée un compte administrateur (tous les droits, paramétrage de base compris) : python manage.py creer_administrateur"""

import getpass

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from compta.vues_utilisateurs import donner_role


class Command(BaseCommand):
    help = "Crée un utilisateur du rôle Administrateur."

    def handle(self, **options):
        nom = input("Identifiant de l'administrateur (nom ou e-mail) : ").strip()
        if not nom or User.objects.filter(username__iexact=nom).exists():
            raise CommandError("Identifiant vide ou déjà utilisé.")
        mdp = getpass.getpass("Mot de passe (12 caractères au moins) : ")
        if len(mdp) < 12 or mdp != getpass.getpass("Encore une fois : "):
            raise CommandError("Mot de passe trop court ou différent.")
        u = User.objects.create_user(nom, nom if "@" in nom else "", mdp)
        donner_role(u, "Administrateur")
        self.stdout.write(self.style.SUCCESS(f"Administrateur « {nom} » créé."))
