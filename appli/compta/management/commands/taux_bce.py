"""python manage.py taux_bce [--depuis AAAA-MM-JJ] : ajoute les cours BCE manquants des devises des journaux."""

import datetime as dt

from django.core.management.base import BaseCommand

from compta import taux


class Command(BaseCommand):
    help = "Cours de change BCE des devises des journaux (tâche planifiée quotidienne possible)."

    def add_arguments(self, parser):
        parser.add_argument("--depuis", type=dt.date.fromisoformat)

    def handle(self, *args, **o):
        self.stdout.write(taux.actualiser(o.get("depuis")))
