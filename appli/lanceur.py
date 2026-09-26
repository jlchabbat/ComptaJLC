"""Lanceur de ComptaBB sur le PC : démarre l'application et ouvre le navigateur.

Au premier lancement : crée la base (dossier data à côté du programme),
demande l'identifiant et le mot de passe du trésorier, et propose de
reprendre les données d'un classeur ComptaBB.xlsm. Ensuite : un double-clic
suffit. L'application reste accessible à l'adresse affichée tant que la
fenêtre est ouverte.
"""

import os
import sys
import threading
import webbrowser
from pathlib import Path

ADRESSE, PORT = "127.0.0.1", int(os.environ.get("COMPTABB_PORT", "8765"))


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "comptabb.settings")
    import django
    django.setup()
    from django.contrib.auth.models import Group, User
    from django.core.management import call_command

    call_command("migrate", verbosity=0)
    call_command("collectstatic", interactive=False, verbosity=0)
    if not User.objects.exists():
        print("Premier lancement : création du compte du trésorier.")
        nom = input("Identifiant : ").strip() or "tresorier"
        import getpass
        while True:
            mdp = getpass.getpass("Mot de passe (8 caractères au moins) : ")
            if len(mdp) >= 8 and mdp == getpass.getpass("Le retaper : "):
                break
            print("Mots de passe trop courts ou différents.")
        u = User.objects.create_superuser(nom, "", mdp)
        u.groups.add(Group.objects.get(name="Trésorier"))
        from compta.models import Mouvement
        if not Mouvement.objects.exists():
            chemin = input("Classeur ComptaBB.xlsm à reprendre (vide pour passer) : ").strip().strip('"')
            if chemin:
                call_command("importer_classeur", chemin)

    from waitress import serve
    from comptabb.wsgi import application
    url = f"http://{ADRESSE}:{PORT}/"
    print(f"ComptaBB est ouvert à l'adresse {url} — fermer cette fenêtre arrête l'application.")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    serve(application, host=ADRESSE, port=PORT, threads=8)


if __name__ == "__main__":
    main()
