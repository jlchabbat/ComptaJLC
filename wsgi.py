"""Point d'entrée WSGI (PythonAnywhere : pointer le fichier WSGI vers `application`)."""
from comptajlc import create_app

application = create_app()
