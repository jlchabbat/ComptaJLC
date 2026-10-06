"""Prépare ou met à jour une installation : base, fichiers statiques, paramètres de saisie.

    python manage.py preparer

À relancer après chaque mise à jour du code (sans risque : rien n'est effacé)."""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Migre la base, rassemble les fichiers statiques et complète les paramètres."

    def handle(self, **options):
        call_command("migrate", verbosity=0)
        call_command("corriger_axes", "--appliquer", verbosity=0)       # anomalies d'axes résiduelles (mise à jour)
        call_command("collectstatic", interactive=False, verbosity=0)
        from compta.saisie import initialiser_parametres
        initialiser_parametres()
        from compta.models import Mouvement
        self.stdout.write(self.style.SUCCESS(f"ComptaJLC prêt : {Mouvement.objects.count()} mouvements dans la base."))
        from compta.demarrage import code_installation
        code = code_installation()                      # site neuf : premier administrateur à créer dans le navigateur
        if code:
            self.stdout.write(self.style.WARNING(
                f"Site neuf : ouvrez le site dans le navigateur et saisissez le code d'installation {code}"))
