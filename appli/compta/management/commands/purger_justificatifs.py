"""Libère la place : python manage.py purger_justificatifs [--confirmer]"""

from django.conf import settings
from django.core.management.base import BaseCommand

from compta import justificatifs
from compta.models import Justificatif, Modification


class Command(BaseCommand):
    help = ("Supprime les fichiers des justificatifs rattachés aux mouvements (et les copies justificatifs_*.zip des "
            "sauvegardes). Les liens en ligne et les écritures sont conservés. Sans --confirmer : simple aperçu.")

    def add_arguments(self, parser):
        parser.add_argument("--confirmer", action="store_true", help="Supprime réellement (irréversible).")

    def handle(self, *args, **options):
        fichiers = Justificatif.objects.exclude(chemin__isnull=True).exclude(chemin="")
        total, presents = 0, 0
        for j in fichiers:
            f = justificatifs.chemin(j)
            if f and f.exists():
                presents += 1
                total += f.stat().st_size
        sauvegardes = list((settings.DATA_DIR / "Exports" / "Sauvegardes").glob("justificatifs_*.zip")) \
            if (settings.DATA_DIR / "Exports" / "Sauvegardes").exists() else []
        self.stdout.write(f"{fichiers.count()} justificatif(s) avec fichier ({presents} présent(s), {total // 1048576} Mo) ; "
                          f"{len(sauvegardes)} copie(s) ZIP de sauvegarde.")
        if not options["confirmer"]:
            self.stdout.write("Aperçu seulement : rien n'est supprimé. Relancer avec --confirmer.")
            return
        n = 0
        for j in fichiers.select_related("mouvement"):
            f = justificatifs.chemin(j)
            Modification.objects.create(auteur="console", lot="Justificatifs", action="Purge d'un justificatif",
                                        objet=f"Mvt {j.mouvement.numero}", avant=f"{j.nom} {j.description}"[:300])
            j.delete()
            if f and f.exists():
                f.unlink()
            n += 1
        for z in sauvegardes:
            z.unlink()
        self.stdout.write(f"{n} justificatif(s) supprimé(s), {len(sauvegardes)} copie(s) ZIP effacée(s).")
