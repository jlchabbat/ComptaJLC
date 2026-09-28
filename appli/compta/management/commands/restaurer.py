"""Remet la base dans l'état d'une sauvegarde (.sqlite3), comptes utilisateurs compris.

    python manage.py restaurer                   liste les sauvegardes (les plus récentes d'abord)
    python manage.py restaurer 3                 restaure la n° 3 de la liste
    python manage.py restaurer derniere          restaure la plus récente
    python manage.py restaurer chemin.sqlite3    restaure ce fichier

Une sauvegarde de la base actuelle est faite juste avant ; la confirmation REMPLACER est demandée (--oui pour s'en passer).
Sur PythonAnywhere : précéder la commande de COMPTABB_DATA=~/comptabb-data (voir le mode d'emploi)."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from compta import base_donnees as bd
from compta.models import Modification


class Command(BaseCommand):
    help = "Restaure la base depuis une sauvegarde (.sqlite3)."

    def add_arguments(self, parser):
        parser.add_argument("sauvegarde", nargs="?", help="n° de la liste, « derniere », nom ou chemin d'un fichier .sqlite3")
        parser.add_argument("--oui", action="store_true", help="ne pas demander de confirmation")

    def handle(self, sauvegarde=None, oui=False, **options):
        liste = bd.liste()
        if not sauvegarde:
            self.stdout.write(f"Sauvegardes dans {bd.dossier()} :")
            for i, p in enumerate(liste, 1):
                self.stdout.write(f"  {i:>2}. {p.name}")
            self.stdout.write("Restaurer : python manage.py restaurer <n°>   (ou « derniere », ou un chemin)")
            return
        if sauvegarde.isdigit() and 1 <= int(sauvegarde) <= len(liste):
            chemin = liste[int(sauvegarde) - 1]
        elif sauvegarde.lower() in ("derniere", "dernière") and liste:
            chemin = liste[0]
        else:
            chemin = next((p for p in liste if p.name == sauvegarde), Path(sauvegarde))
        if not chemin.is_file():
            raise CommandError(f"Sauvegarde introuvable : {sauvegarde}")
        try:
            n = bd.verifier(chemin)
        except ValueError as e:
            raise CommandError(str(e)) from None
        self.stdout.write(f"Restaurer {chemin.name} ({n} mouvements) : toute la base actuelle sera remplacée.")
        if not oui and input("Tapez REMPLACER pour confirmer : ").strip().upper() != "REMPLACER":
            raise CommandError("Abandon : rien n'a été modifié.")
        n, avant = bd.restaurer(chemin)
        Modification.objects.create(auteur="ligne de commande", lot="Base de données", action="Restauration",
                                    objet=chemin.name, apres=f"{n} mouvements ; sauvegarde préalable {avant.name}")
        self.stdout.write(self.style.SUCCESS(f"Base restaurée depuis {chemin.name} ({n} mouvements)."))
        self.stdout.write(f"Sauvegarde de l'état précédent : {avant}")
