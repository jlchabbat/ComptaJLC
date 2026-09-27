"""Paramètres de ComptaBB dans Imports/Parametres.xlsx (modifiable dans Excel, puis réinjecté).

    python manage.py parametres exporter [fichier]     écrit le classeur (défaut : Imports/Parametres.xlsx)
    python manage.py parametres importer [fichier]     réinjecte le classeur (sauvegarde de la base d'abord)

Réservé à qui a accès au serveur ; sur le site, à l'administrateur et au trésorier.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from compta import base_donnees as bd
from compta import dossiers
from compta import parametres as moteur


def chemin_defaut():
    return dossiers.imports() / moteur.NOM_FICHIER


class Command(BaseCommand):
    help = "Exporte ou importe le classeur Imports/Parametres.xlsx."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["exporter", "importer"])
        parser.add_argument("fichier", nargs="?", help=f"défaut : Imports/{moteur.NOM_FICHIER}")

    def handle(self, action, fichier=None, **options):
        chemin = Path(fichier) if fichier else chemin_defaut()
        if action == "exporter":
            chemin.parent.mkdir(parents=True, exist_ok=True)
            try:
                chemin.write_bytes(moteur.contenu_classeur())
            except PermissionError:
                raise CommandError(f"{chemin} est ouvert dans Excel : fermez-le puis recommencez.") from None
            self.stdout.write(self.style.SUCCESS(f"Paramètres exportés : {chemin}"))
            return
        if not chemin.exists():
            raise CommandError(f"Fichier introuvable : {chemin}")
        sauvegarde = bd.sauvegarder("avant_import_parametres")
        rapport = moteur.importer(chemin.read_bytes(), auteur="ligne de commande")
        if rapport.erreurs:
            for e in rapport.erreurs:
                self.stderr.write(f"  {e}")
            raise CommandError(f"{len(rapport.erreurs)} ligne(s) à corriger : rien n'a été enregistré.")
        for e in rapport.crees:
            self.stdout.write(f"  créé    {e}")
        for e in rapport.modifies:
            self.stdout.write(f"  modifié {e}")
        self.stdout.write(self.style.SUCCESS(f"Import terminé : {rapport.resume}. Sauvegarde préalable : {sauvegarde.name}"))
