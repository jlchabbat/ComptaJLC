"""Licences des sites des associations (côté éditeur, sur votre propre compte seulement).

    python manage.py licence cles                       crée la paire de clés (une seule fois) dans ~/comptajlc-licence
    python manage.py licence creer --association "Amis du musée" --site amisdumusee.pythonanywhere.com --fin 2027-12-31
    python manage.py licence verifier "CBB1.…"          affiche le contenu d'une licence

La clé privée (~/comptajlc-licence/privee.pem) ne doit jamais quitter votre compte ni entrer dans le dépôt : qui l'a
peut créer des licences. La clé publique s'inscrit dans compta/licence.py (CLE_PUBLIQUE)."""

import datetime as dt
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from compta import licence


class Command(BaseCommand):
    help = "Crée la paire de clés de l'éditeur, crée ou vérifie une licence."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["cles", "creer", "verifier"])
        parser.add_argument("texte", nargs="?", default="")
        parser.add_argument("--association", default="")
        parser.add_argument("--site", default="", help="adresse du site (ex. amisdumusee.pythonanywhere.com) ou * pour tout site")
        parser.add_argument("--fin", default="", help="dernier jour de validité, AAAA-MM-JJ")
        parser.add_argument("--dossier", default=str(Path.home() / "comptajlc-licence"))

    def handle(self, action, texte, association, site, fin, dossier, **o):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        d = Path(dossier)
        privee = d / "privee.pem"
        if action == "cles":
            if privee.exists():
                raise CommandError(f"{privee} existe déjà : ne pas le remplacer (les licences déjà données ne vaudraient plus rien).")
            d.mkdir(parents=True, exist_ok=True)
            cle = Ed25519PrivateKey.generate()
            privee.write_bytes(cle.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                 serialization.NoEncryption()))
            privee.chmod(0o600)
            publique = licence._b64(cle.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
            (d / "publique.txt").write_text(publique + "\n", encoding="utf-8")
            self.stdout.write(f"Clé privée : {privee} (à garder secrète, et à sauvegarder hors du site).")
            self.stdout.write(self.style.SUCCESS(f"Clé publique (à inscrire dans compta/licence.py, CLE_PUBLIQUE) : {publique}"))
            return
        if action == "creer":
            if not privee.exists():
                raise CommandError(f"Pas de clé privée ({privee}) : commencer par « python manage.py licence cles ».")
            if not (association and site and fin):
                raise CommandError("Indiquer --association, --site et --fin.")
            try:
                date_fin = dt.date.fromisoformat(fin)
            except ValueError:
                raise CommandError("--fin : date AAAA-MM-JJ.")
            cle = serialization.load_pem_private_key(privee.read_bytes(), password=None)
            self.stdout.write(licence.signer(cle, association, site.lower(), date_fin))
            return
        publique = (d / "publique.txt").read_text(encoding="utf-8").strip() if (d / "publique.txt").exists() else None
        try:
            lic = licence.lire(texte, publique)
        except licence.LicenceInvalide as e:
            raise CommandError(str(e))
        self.stdout.write(f"Association : {lic['association']} · site : {lic['site']} · fin : {lic['fin']:%d/%m/%Y}")
