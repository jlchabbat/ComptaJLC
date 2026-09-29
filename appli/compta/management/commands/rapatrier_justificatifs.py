"""Copie sur le site les documents des justificatifs « lien » : python manage.py rapatrier_justificatifs"""

from django.core.management.base import BaseCommand

from compta import justificatifs


class Command(BaseCommand):
    help = "Copie sur le site les documents encore en ligne (liens) ; le lien est ensuite oublié."

    def handle(self, *args, **options):
        faits, erreurs, restent = justificatifs.rapatrier_tous("console")
        for e in erreurs:
            self.stdout.write(f"  {e}")
        self.stdout.write(f"{faits} document(s) copié(s) sur le site ; {restent} lien(s) restant(s).")
