"""Dépose des justificatifs existants (dossier, ZIP ou fichiers) dans « à classer » et affiche les rattachements proposés.

    python manage.py importer_justificatifs Scans/            dépose et liste les propositions
    python manage.py importer_justificatifs Scans.zip --rattacher   rattache en plus les propositions sûres

La vérification et le rattachement des autres se font sur la page Saisie › Justificatifs.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from compta import justificatifs as moteur
from compta.models import Mouvement


class Command(BaseCommand):
    help = "Dépose des justificatifs existants et propose leur mouvement d'après le nom du fichier."

    def add_arguments(self, parser):
        parser.add_argument("chemins", nargs="+", help="dossier, fichier ZIP ou fichiers PDF / images")
        parser.add_argument("--rattacher", action="store_true", help="rattacher les propositions sûres")

    def handle(self, chemins, rattacher=False, **options):
        refus = []
        for c in map(Path, chemins):
            if not c.exists():
                raise CommandError(f"Introuvable : {c}")
            fichiers = sorted(p for p in c.rglob("*") if p.is_file()) if c.is_dir() else [c]
            for f in fichiers:
                nom = str(f.relative_to(c.parent)) if c.is_dir() else f.name
                refus += moteur.deposer(nom, f.read_bytes())[1]
        for e in refus:
            self.stderr.write(f"  refusé : {e}")
        faits = 0
        for l in moteur.a_classer():
            m = l["mouvement"]
            if rattacher and l["sur"]:
                j = moteur.rattacher(l["nom"], m, auteur="ligne de commande")
                autres = [Mouvement.objects.get(numero=n) for n in moteur.numeros(l.get("saisie", ""))[1:]]
                for autre in autres:                      # « 389+412 facture.pdf » : aussi joint aux suivants
                    moteur.copier(j, autre, "ligne de commande")
                faits += 1
                cibles = "+".join(str(x.numero) for x in [m] + autres)
                self.stdout.write(f"  rattaché   {l['affiche']} → Mvt {cibles} ({l['raison']})")
            else:
                cible = f"Mvt {m.numero}" if m else "?"
                self.stdout.write(f"  à classer  {l['affiche']} → {cible} ({l['raison']})")
        self.stdout.write(self.style.SUCCESS(
            f"{faits} rattaché(s) ; le reste se vérifie sur la page Saisie › Justificatifs."))
