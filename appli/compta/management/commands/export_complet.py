"""Export complet en une opération : Exports/Export_complet_<date>.zip.

    python manage.py export_complet

Contient la sauvegarde de la base, Parametres.xlsx, Tiers.xlsx, Donnees.xlsx, les états de chaque exercice et
controle.json (nombres et totaux). Se réinjecte avec « manage.py reinjecter ».
"""

from django.core.management.base import BaseCommand

from compta import export_complet


class Command(BaseCommand):
    help = "Crée un export complet (ZIP) dans le dossier Exports."

    def handle(self, **options):
        chemin = export_complet.exporter(auteur="ligne de commande")
        self.stdout.write(self.style.SUCCESS(f"Export complet : {chemin}"))
