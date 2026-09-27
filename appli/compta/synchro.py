"""« Recevoir la base du site » : sur le PC, remplace la base locale par une copie de celle du site.

Le PC se connecte au site comme un navigateur, avec l'identifiant et le mot de passe d'un administrateur du site
(rien n'est enregistré), télécharge la base (Base de données › Télécharger la base maintenant), la vérifie, puis la
recharge. La base du PC est sauvegardée juste avant. Sens unique : du site vers le PC."""

import http.cookiejar
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import base_donnees as bd

ADRESSE_PAR_DEFAUT = "https://comptabb.pythonanywhere.com"
DELAI = 120


class Navigateur:
    """Petit navigateur : cookies de session, en-tête Referer (exigé par la protection CSRF en HTTPS)."""

    def __init__(self):
        self.ouvreur = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(self, url):
        """(statut, adresse finale, contenu)"""
        try:
            with self.ouvreur.open(urllib.request.Request(url), timeout=DELAI) as r:
                return r.status, r.geturl(), r.read()
        except urllib.error.HTTPError as e:
            return e.code, url, b""

    def post(self, url, donnees):
        req = urllib.request.Request(url, data=urllib.parse.urlencode(donnees).encode(), headers={"Referer": url})
        try:
            with self.ouvreur.open(req, timeout=DELAI) as r:
                return r.status, r.geturl(), r.read()
        except urllib.error.HTTPError as e:
            return e.code, url, b""


def adresse_valide(adresse):
    adresse = (adresse or "").strip().rstrip("/")
    p = urllib.parse.urlparse(adresse)
    local = p.hostname in ("127.0.0.1", "localhost")
    if p.scheme not in ("https", "http") or not p.hostname or (p.scheme == "http" and not local):
        raise ValueError("Adresse du site attendue en https://…, par exemple " + ADRESSE_PAR_DEFAUT + ".")
    return adresse


def telecharger(adresse, identifiant, mot_de_passe, navigateur=None):
    """Se connecte au site et télécharge une copie de sa base ; renvoie le chemin du fichier."""
    adresse = adresse_valide(adresse)
    nav = navigateur or Navigateur()
    try:
        statut, _, page = nav.get(adresse + "/connexion/")
        jeton = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page)
        if statut != 200 or not jeton:
            raise ValueError(f"Pas de page de connexion ComptaBB à l'adresse {adresse}.")
        statut, finale, _ = nav.post(adresse + "/connexion/", {"csrfmiddlewaretoken": jeton.group(1).decode(),
                                                                "username": identifiant.strip(), "password": mot_de_passe})
        if statut == 200 and finale.rstrip("/").endswith("/connexion"):
            raise ValueError(f"Le site a refusé l'identifiant « {identifiant.strip()} » ou son mot de passe. Vérifiez-les en vous "
                             f"connectant au site dans le navigateur ({adresse}) : ce sont ceux du site, pas forcément ceux du PC.")
        if statut != 200:
            raise ValueError(f"Le site a refusé la connexion (erreur {statut}), sans lien avec le mot de passe. "
                             "Mettre à jour le site et le PC avec la même version, puis réessayer.")
        statut, _, contenu = nav.get(adresse + "/base/telecharger/")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ValueError(f"Site injoignable ({getattr(e, 'reason', e)}). Vérifier la connexion internet et l'adresse.") from None
    if statut == 403:
        raise ValueError("Ce compte n'est pas administrateur sur le site : seul un administrateur peut copier la base.")
    if statut != 200 or not contenu.startswith(b"SQLite format 3"):
        raise ValueError("Le site n'a pas envoyé de base de données.")
    chemin = Path(tempfile.mkdtemp()) / "base_du_site.sqlite3"
    chemin.write_bytes(contenu)
    return chemin


def recevoir(adresse, identifiant, mot_de_passe, navigateur=None):
    """Télécharge la base du site, la vérifie et remplace la base locale ; renvoie (mouvements, sauvegarde d'avant)."""
    chemin = telecharger(adresse, identifiant, mot_de_passe, navigateur)
    bd.verifier(chemin)
    n, avant = bd.restaurer(chemin)
    from .models import Modification, Reglage
    Reglage.objects.update_or_create(cle="adresse_site", defaults={"valeur": adresse_valide(adresse),
                                                                    "description": "Adresse du site (Recevoir la base du site)"})
    Modification.objects.create(auteur=identifiant, lot="Base de données", action="Base reçue du site", objet=adresse[:200],
                                apres=f"{n} mouvements ; sauvegarde du PC d'avant {avant.name}")
    return n, avant
