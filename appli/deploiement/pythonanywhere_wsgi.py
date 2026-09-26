# Fichier WSGI pour PythonAnywhere : copier ce contenu dans le fichier WSGI
# de l'application web (onglet Web), puis remplacer VOTRE_NOM par votre
# identifiant PythonAnywhere (3 endroits).
import os
import sys

sys.path.insert(0, "/home/VOTRE_NOM/ComptaBB/appli")
os.environ["DJANGO_SETTINGS_MODULE"] = "comptabb.settings"
os.environ["COMPTABB_DATA"] = "/home/VOTRE_NOM/comptabb-data"
os.environ["COMPTABB_HOTES"] = "VOTRE_NOM.pythonanywhere.com"
os.environ["COMPTABB_HTTPS"] = "1"

from django.core.wsgi import get_wsgi_application  # noqa: E402

application = get_wsgi_application()
