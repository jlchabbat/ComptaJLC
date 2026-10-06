# Fichier WSGI pour PythonAnywhere : copier ce contenu dans le fichier WSGI
# de l'application web (onglet Web), puis remplacer VOTRE_NOM par votre
# identifiant PythonAnywhere (3 endroits).
import os
import sys

sys.path.insert(0, "/home/VOTRE_NOM/ComptaJLC/appli")
os.environ["DJANGO_SETTINGS_MODULE"] = "comptajlc.settings"
os.environ["COMPTAJLC_DATA"] = "/home/VOTRE_NOM/comptajlc-data"
os.environ["COMPTAJLC_HOTES"] = "VOTRE_NOM.pythonanywhere.com"
os.environ["COMPTAJLC_HTTPS"] = "1"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
