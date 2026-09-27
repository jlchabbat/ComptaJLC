"""Remet la comptabilité à zéro et recharge un export complet, puis vérifie que la base est identique à l'export.

    python manage.py reinjecter Exports/Export_complet_<date>.zip

Une sauvegarde de la base est faite d'abord ; au moindre écart, rien n'est modifié. Les comptes utilisateurs sont gardés.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from compta import export_complet


class Command(BaseCommand):
    help = "Remet à zéro et recharge un export complet (ZIP)."

    def add_arguments(self, parser):
        parser.add_argument("export", help="fichier Export_complet_….zip")

    def handle(self, export, **options):
        if not Path(export).exists():
            raise CommandError(f"Fichier introuvable : {export}")
        try:
            message, avant = export_complet.reinjecter(export, auteur="ligne de commande")
        except export_complet.ExportInvalide as e:
            raise CommandError(f"{e}\nRien n'a été modifié.") from None
        self.stdout.write(self.style.SUCCESS(message))
        self.stdout.write(f"Sauvegarde préalable : {avant.name}")
