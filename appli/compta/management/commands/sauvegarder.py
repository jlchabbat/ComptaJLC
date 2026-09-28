"""Sauvegarde datée de la base : python manage.py sauvegarder

Pour une sauvegarde automatique quotidienne sur PythonAnywhere (onglet Tasks) :
COMPTABB_DATA=/home/ComptaBB/comptabb-data /home/ComptaBB/venv/bin/python /home/ComptaBB/ComptaBB/appli/manage.py sauvegarder
Les 3 dernières sauvegardes sont gardées dans Exports/Sauvegardes."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crée une sauvegarde datée de la base dans Exports/Sauvegardes."

    def add_arguments(self, parser):
        parser.add_argument("--motif", default="auto")

    def handle(self, motif="auto", **options):
        from compta.base_donnees import sauvegarder
        from compta.models import Modification
        chemin = sauvegarder(motif)
        Modification.objects.create(auteur="Tâche planifiée", lot="Base de données", action="Sauvegarde", objet=chemin.name)
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde : {chemin}"))
