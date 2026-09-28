"""Réglages de l'application ComptaBB.

Les données (base SQLite, clé secrète) vivent dans un dossier `data` à côté
de l'application — ou de l'exécutable une fois empaqueté — sauf si la
variable d'environnement COMPTABB_DATA en désigne un autre. Aucun chemin
absolu n'est codé en dur.

Hébergement (docs/hebergement-pythonanywhere.md) : COMPTABB_DATA (dossier des
données), COMPTABB_HOTES (nom du site) et COMPTABB_HTTPS=1 (cookies sécurisés,
redirection HTTPS) se règlent dans le fichier WSGI de l'hébergeur.
"""

import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RACINE = BASE_DIR.parent
DATA_DIR = Path(os.environ.get("COMPTABB_DATA", RACINE / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
# Dossiers d'échange (administrateur) : Imports (fichiers à importer) et Exports (sauvegardes, archives, exports).
# Sur l'hébergeur : dans le dossier des données, pour survivre aux mises à jour du code.
_ECHANGES = DATA_DIR if os.environ.get("COMPTABB_DATA") else RACINE
IMPORTS_DIR = Path(os.environ.get("COMPTABB_IMPORTS", _ECHANGES / "Imports"))
EXPORTS_DIR = Path(os.environ.get("COMPTABB_EXPORTS", _ECHANGES / "Exports"))


def _cle_secrete():
    if os.environ.get("COMPTABB_SECRET"):
        return os.environ["COMPTABB_SECRET"]
    fichier = DATA_DIR / "secret.txt"
    if not fichier.exists():
        fichier.write_text(secrets.token_urlsafe(50), encoding="utf-8")
    return fichier.read_text(encoding="utf-8").strip()


SECRET_KEY = _cle_secrete()
DEBUG = os.environ.get("COMPTABB_DEBUG") == "1"
ALLOWED_HOSTS = os.environ.get("COMPTABB_HOTES", "127.0.0.1,localhost").split(",")

if os.environ.get("COMPTABB_HTTPS") == "1":
    CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS]
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 3600
    SESSION_COOKIE_AGE = 8 * 3600          # reconnexion après 8 heures

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "compta",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "compta.export_pages.ExportExcelMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "comptabb.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "compta.reglages.contexte",
    ]},
}]
WSGI_APPLICATION = "comptabb.wsgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DATA_DIR / "comptabb.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Asia/Jerusalem"
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

STATIC_URL = "static/"
STATIC_ROOT = DATA_DIR / "static"
STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"}}
WHITENOISE_USE_FINDERS = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTHENTICATION_BACKENDS = ["compta.vues_utilisateurs.ConnexionParEmail"]
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "tableau_de_bord"
LOGOUT_REDIRECT_URL = "login"

# Justificatifs « lien » (SUMIT…) : copier aussitôt le document sur le site (pas pendant les tests : pas de réseau)
RAPATRIER_LIENS = "test" not in sys.argv
