"""Prépare ou met à jour une installation : base, fichiers statiques, paramètres de saisie.

    python manage.py preparer

À relancer après chaque mise à jour du code (sans risque : rien n'est effacé)."""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Migre la base, rassemble les fichiers statiques et complète les paramètres."

    def handle(self, **options):
        call_command("migrate", verbosity=0)
        call_command("collectstatic", interactive=False, verbosity=0)
        from compta.saisie import initialiser_parametres
        initialiser_parametres()
        from compta.models import Mouvement
        self.stdout.write(self.style.SUCCESS(f"ComptaBB prêt : {Mouvement.objects.count()} mouvements dans la base."))
