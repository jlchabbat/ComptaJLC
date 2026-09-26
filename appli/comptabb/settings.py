"""Réglages de l'application ComptaBB.

Les données (base SQLite, clé secrète) vivent dans un dossier `data` à côté
de l'application — ou de l'exécutable une fois empaqueté — sauf si la
variable d'environnement COMPTABB_DATA en désigne un autre. Aucun chemin
absolu n'est codé en dur. Pour un hébergement, DATABASE_URL et
COMPTABB_HOTES remplaceront ces valeurs locales.
"""

import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FIGE = getattr(sys, "frozen", False)
RACINE = Path(sys.executable).resolve().parent if FIGE else BASE_DIR.parent
DATA_DIR = Path(os.environ.get("COMPTABB_DATA", RACINE / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)


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
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "tableau_de_bord"
LOGOUT_REDIRECT_URL = "login"
