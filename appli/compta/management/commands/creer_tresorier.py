"""Crée un compte trésorier (tenue des comptes, sans le paramétrage de base) : python manage.py creer_tresorier

Le premier compte à créer est l'administrateur (python manage.py creer_administrateur) ; il peut ensuite créer
les trésoriers depuis Administration › Utilisateurs."""

import getpass

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from compta.vues_utilisateurs import donner_role


class Command(BaseCommand):
    help = "Crée un utilisateur du rôle Trésorier."

    def handle(self, **options):
        nom = input("Identifiant du trésorier (nom ou e-mail) : ").strip()
        if not nom or User.objects.filter(username__iexact=nom).exists():
            raise CommandError("Identifiant vide ou déjà utilisé.")
        mdp = getpass.getpass("Mot de passe (12 caractères au moins) : ")
        if len(mdp) < 12 or mdp != getpass.getpass("Encore une fois : "):
            raise CommandError("Mot de passe trop court ou différent.")
        u = User.objects.create_user(nom, nom if "@" in nom else "", mdp)
        donner_role(u, "Trésorier")
        self.stdout.write(self.style.SUCCESS(f"Trésorier « {nom} » créé."))
