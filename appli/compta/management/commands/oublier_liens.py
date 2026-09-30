"""Le document est sur le PC : python manage.py oublier_liens --contient TEXTE [--confirmer]"""

from django.core.management.base import BaseCommand, CommandError

from compta.models import Justificatif, Modification


class Command(BaseCommand):
    help = ("Pour les justificatifs « lien » dont l'adresse contient TEXTE : efface l'adresse et renomme le justificatif "
            "« <n° de Mvt> document » (comme le script du PC). Le justificatif reste rattaché à l'écriture ; ancienne "
            "adresse et ancien nom sont gardés dans le journal des modifications. Sans --confirmer : aperçu seulement.")

    def add_arguments(self, parser):
        parser.add_argument("--contient", required=True, help="Partie de l'adresse à retirer (ex. nom de l'hébergeur).")
        parser.add_argument("--confirmer", action="store_true", help="Applique réellement.")

    def handle(self, *args, **options):
        texte = options["contient"].strip()
        if len(texte) < 3:
            raise CommandError("--contient : au moins 3 caractères.")
        liens = Justificatif.objects.filter(lien__icontains=texte).select_related("mouvement") \
            .order_by("mouvement__numero", "id")
        rang, prevus = {}, []
        for j in liens:
            n = j.mouvement.numero
            rang[n] = rang.get(n, 0) + 1
            prevus.append((j, f"{n} document" + ("" if rang[n] == 1 else f" ({rang[n]})")))
        for j, nouveau in prevus:
            self.stdout.write(f"  Mvt {j.mouvement.numero} : « {j.nom} » -> « {nouveau} »")
        self.stdout.write(f"{len(prevus)} justificatif(s) concerné(s).")
        if not options["confirmer"]:
            self.stdout.write("Aperçu seulement : rien n'est modifié. Relancer avec --confirmer.")
            return
        for j, nouveau in prevus:
            Modification.objects.create(auteur="console", lot="Justificatifs", action="Adresse d'un justificatif retirée",
                                        objet=f"Mvt {j.mouvement.numero}", avant=f"{j.nom} {j.lien}"[:300], apres=nouveau)
            j.nom, j.lien = nouveau, ""
            j.save(update_fields=["nom", "lien"])
        self.stdout.write(f"{len(prevus)} justificatif(s) renommé(s), adresse retirée.")
