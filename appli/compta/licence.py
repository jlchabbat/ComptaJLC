"""Clé de licence des sites créés par l'assistant de premier démarrage (un site par association, étape 3).

- Sites d'avant l'assistant (celui de la Loge) : jamais de licence demandée.
- Site neuf : ESSAI_JOURS jours d'essai à partir du démarrage, puis une licence signée (association, site, date de fin).
- Sans licence valide : lecture seule. On consulte, imprime et exporte (export complet compris), on ne saisit plus.

La licence est signée (Ed25519) par la clé privée de l'éditeur, créée par « python manage.py licence cles » dans un
dossier hors du dépôt et hors des données ; seule la clé publique (CLE_PUBLIQUE) est dans le code. Tant qu'elle est
vide, aucune licence n'est demandée nulle part."""

import base64
import datetime as dt
import json

from django.conf import settings

from .models import Reglage

CLE_PUBLIQUE = ""              # clé publique de l'éditeur (base64), affichée par « python manage.py licence cles »
ESSAI_JOURS = 60
PREFIXE = "CBB1"
# actions permises en lecture seule : exports, sauvegardes, connexion, licence, mot de passe
CHEMINS_LIBRES = ("/licence/", "/connexion/", "/deconnexion/", "/mon-compte/", "/demarrage/")
ACTIONS_LIBRES = ("export_complet", "exporter", "tout_sauvegarder", "sauvegarder")


class LicenceInvalide(ValueError):
    pass


def _b64(octets):
    return base64.urlsafe_b64encode(octets).decode().rstrip("=")


def _deb64(texte):
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def signer(cle_privee, association, site, fin):
    """Texte de la licence (côté éditeur) : CBB1.<contenu>.<signature>."""
    contenu = _b64(json.dumps({"a": association, "s": site, "f": fin.isoformat()}, ensure_ascii=False).encode())
    return f"{PREFIXE}.{contenu}.{_b64(cle_privee.sign(contenu.encode()))}"


def lire(texte, cle_publique=None):
    """{association, site, fin} d'une licence dont la signature est bonne ; LicenceInvalide sinon."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        prefixe, contenu, signature = "".join(texte.split()).split(".")
        if prefixe != PREFIXE:
            raise ValueError
        cle = Ed25519PublicKey.from_public_bytes(_deb64(cle_publique or CLE_PUBLIQUE))
        cle.verify(_deb64(signature), contenu.encode())
        d = json.loads(_deb64(contenu))
        return {"association": d["a"], "site": d["s"], "fin": dt.date.fromisoformat(d["f"])}
    except (ValueError, KeyError, TypeError, InvalidSignature):
        raise LicenceInvalide("Licence illisible ou falsifiée : recopiez-la exactement, en entier.")


def sites():
    return [h.lower() for h in settings.ALLOWED_HOSTS]


def etat(aujourdhui=None):
    """{code, message, lecture_seule, licence} ; code : exempt, essai, valide, expiree, invalide."""
    if not CLE_PUBLIQUE or Reglage.lire("demarrage") != "fait":
        return {"code": "exempt", "message": "", "lecture_seule": False, "licence": None}
    aujourdhui = aujourdhui or dt.date.today()
    texte = Reglage.lire("licence")
    if texte:
        try:
            lic = lire(texte)
        except LicenceInvalide as e:
            return {"code": "invalide", "message": f"{e} Site en lecture seule.", "lecture_seule": True, "licence": None}
        if lic["site"] != "*" and lic["site"].lower() not in sites():
            return {"code": "invalide", "message": f"Cette licence est celle du site {lic['site']}. Site en lecture seule.",
                    "lecture_seule": True, "licence": lic}
        reste = (lic["fin"] - aujourdhui).days
        if reste < 0:
            return {"code": "expiree", "message": f"Licence expirée le {lic['fin']:%d/%m/%Y} : site en lecture seule "
                    "(consultation et exports seulement).", "lecture_seule": True, "licence": lic}
        return {"code": "valide", "lecture_seule": False, "licence": lic,
                "message": f"Licence valable jusqu'au {lic['fin']:%d/%m/%Y} ({reste} jours)." if reste <= 30 else ""}
    try:
        debut = dt.date.fromisoformat(Reglage.lire("demarrage_le"))
    except ValueError:
        debut = aujourdhui
    fin = debut + dt.timedelta(days=ESSAI_JOURS)
    reste = (fin - aujourdhui).days
    if reste < 0:
        return {"code": "expiree", "message": f"Période d'essai terminée le {fin:%d/%m/%Y} : site en lecture seule "
                "(consultation et exports seulement). Saisir la licence : Administration › Licence.",
                "lecture_seule": True, "licence": None}
    return {"code": "essai", "lecture_seule": False, "licence": None,
            "message": f"Période d'essai : {reste} jour(s) restant(s), jusqu'au {fin:%d/%m/%Y}."}


class LicenceMiddleware:
    """Lecture seule sans licence valide : tout envoi de formulaire est refusé, sauf exports, sauvegardes et licence."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (request.method == "POST" and CLE_PUBLIQUE and not request.path.startswith(CHEMINS_LIBRES)
                and not any(a in request.POST for a in ACTIONS_LIBRES)):
            e = etat()
            if e["lecture_seule"]:
                from django.contrib import messages
                from django.shortcuts import redirect
                messages.error(request, e["message"])
                return redirect(request.path)
        return self.get_response(request)


def contexte(request):
    """Bandeau de la licence (essai, expiration proche, lecture seule) pour les administrateurs, dans tous les gabarits."""
    if not CLE_PUBLIQUE or not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    try:
        e = etat()
    except Exception:                                    # base pas encore créée
        return {}
    return {"licence_etat": e} if e["code"] != "exempt" else {}
