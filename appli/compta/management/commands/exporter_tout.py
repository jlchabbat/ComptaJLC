"""Jeu complet d'exports (dossier Exports) et sauvegarde de la base (dossier Sauvegardes) : python manage.py exporter_tout"""

from django.core.management.base import BaseCommand

from compta import echanges


class Command(BaseCommand):
    help = "Écrit tous les fichiers d'export et une sauvegarde de la base dans les dossiers paramétrés."

    def handle(self, **options):
        ecrits, sauvegarde = echanges.tout_exporter("commande exporter_tout")
        for f in ecrits:
            self.stdout.write(f"  {f}")
        self.stdout.write(self.style.SUCCESS(f"{len(ecrits)} fichiers exportés ; sauvegarde : {sauvegarde}"))
