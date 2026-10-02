"""Assistant de premier démarrage d'un site neuf (un site par association, étape 2).

1. Site sans aucun utilisateur : création du premier administrateur, protégée par le code d'installation affiché par
   « python manage.py preparer » (fichier code_installation.txt du dossier des données, effacé ensuite).
2. Base sans journal : l'administrateur décrit l'association (nom, devise, exercice, banques et caisse, options) et
   choisit un plan comptable de base ou l'import de ses propres fichiers (modèles vierges).
Le site de la Loge (déjà des journaux) n'est jamais concerné."""

import datetime as dt
import secrets

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import redirect

from .models import CodeAnalytique, Compte, Exercice, Journal, Modification, Mouvement, Prefixe, Reglage, TypeTiers

FICHIER_CODE = "code_installation.txt"
FORMATS_RELEVE = [("excel", "Excel ou CSV"), ("mizrahi", "PDF Mizrahi-Tefahot (hébreu)"), ("bit", "Bit")]

# plan de base : codes axe 1, préfixes, comptes (numéro, libellé, code axe 1, lettrable) ; 401000 et 411000 donnent
# leur code axe 1 aux comptes de tiers créés ensuite (401…, 411…)
AXE1 = [("BIL.1", "FONDS ASSOCIATIFS"), ("BIL.4", "TIERS"), ("BIL.5", "TRESORERIE"), ("FON.1", "FONCTIONNEMENT"),
        ("ACT.1", "ACTIVITES"), ("COT.1", "COTISATIONS"), ("DON.1", "DONS ET SUBVENTIONS")]
AXE2 = [("GEN.001", "GENERAL")]
PREFIXES = [("ACT.", 1, "Activités"), ("GEN.", 2, "Général"), ("MAN.", 2, "Manifestations"), ("PRO.", 2, "Projets")]
COMPTES = [
    ("110000", "REPORT A NOUVEAU", "BIL.1", False), ("401000", "FOURNISSEURS DIVERS", "BIL.4", True),
    ("411000", "MEMBRES DIVERS", "BIL.4", True),
    ("470000", "COMPTE D'ATTENTE", "BIL.4", False), ("580000", "VIREMENTS INTERNES", "BIL.5", False),
    ("600000", "ACHATS ET FRAIS DIVERS", "FON.1", False), ("600100", "FRAIS BANCAIRES", "FON.1", False),
    ("600200", "LOCATION DE SALLES", "ACT.1", False), ("610000", "MANIFESTATIONS", "ACT.1", False),
    ("625000", "DONS VERSES", "DON.1", False), ("630000", "AIDES VERSEES", "DON.1", False),
    ("700000", "COTISATIONS", "COT.1", False), ("710000", "PARTICIPATIONS AUX MANIFESTATIONS", "ACT.1", False),
    ("720000", "AUTRES RECETTES", "ACT.1", False), ("725000", "DONS RECUS", "DON.1", False),
    ("740000", "SUBVENTIONS", "DON.1", False), ("750000", "PRODUITS FINANCIERS", "FON.1", False),
]
JOURNAUX = [("VT", "Ventes et recettes", "VT"), ("HA", "Achats", "HA"), ("OD", "Opérations diverses", "OD"),
            ("AN", "À-nouveaux", "AN")]


# ---------------------------------------------------------------- étape 1 : premier administrateur

def chemin_code():
    return settings.DATA_DIR / FICHIER_CODE


def code_installation():
    """Code du site neuf (créé au besoin) ; aucun tant qu'un utilisateur existe."""
    if User.objects.exists():
        return ""
    p = chemin_code()
    if not p.exists():
        p.write_text(secrets.token_hex(4).upper(), encoding="utf-8")
    return p.read_text(encoding="utf-8").strip()


def code_valide(saisi):
    p = chemin_code()
    return p.exists() and secrets.compare_digest(saisi.strip().upper(), p.read_text(encoding="utf-8").strip())


def creer_administrateur(identifiant, mot_de_passe):
    from .vues_utilisateurs import donner_role
    u = User.objects.create_user(identifiant, identifiant if "@" in identifiant else "", mot_de_passe)
    donner_role(u, "Administration")
    chemin_code().unlink(missing_ok=True)
    Modification.objects.create(auteur=identifiant, lot="Démarrage", action="Premier administrateur", objet=identifiant)
    return u


# ---------------------------------------------------------------- étape 2 : description de l'association

def a_faire():
    """Base neuve : pas encore de journal ni d'écriture, et l'assistant n'a pas été passé."""
    return not (Journal.objects.exists() or Mouvement.objects.exists() or Reglage.lire("demarrage") == "fait")


def _reglage(cle, valeur, description=""):
    from .reglages import REGLAGES
    description = description or next((d for c, d, *_ in REGLAGES if c == cle), "")
    Reglage.objects.update_or_create(cle=cle, defaults={"valeur": valeur, "description": description})


@transaction.atomic
def demarrer(d, auteur=""):
    """d : données du formulaire (nom, devise, debut, fin, banques [(nom, format)], caisse, carte, hebergeur,
    traductions, plan « base » ou « importer »). Renvoie la liste de ce qui a été créé."""
    fait = []
    _reglage("nom_association", d["nom"])
    _reglage("devise", d["devise"])
    _reglage("carte_bancaire", d.get("carte", ""))
    _reglage("hebergeur_liens", d.get("hebergeur", ""))
    _reglage("traductions_releve", "oui" if d.get("traductions") else "non")
    fait.append("réglages de l'association")
    from .saisie import TYPES_TIERS                       # types de tiers (411 membres, 401 fournisseurs) : dans les deux cas
    for lib, pref in TYPES_TIERS:
        TypeTiers.objects.get_or_create(libelle=lib, defaults={"prefixe": pref})
    if d["plan"] == "base":
        debut, fin = d["debut"], d["fin"]
        libelle = str(debut.year) if debut.year == fin.year else f"{debut.year}-{fin.year}"
        Exercice.objects.get_or_create(debut=debut, defaults={"libelle": libelle, "fin": fin})
        for code, lib in AXE1:
            CodeAnalytique.objects.get_or_create(code=code, defaults={"axe": 1, "libelle": lib})
        for code, lib in AXE2:
            CodeAnalytique.objects.get_or_create(code=code, defaults={"axe": 2, "libelle": lib})
        for p, axe, lib in PREFIXES:
            Prefixe.objects.get_or_create(prefixe=p, defaults={"axe": axe, "libelle": lib})
        for numero, lib, a1, lettrable in COMPTES:
            Compte.objects.get_or_create(numero=numero, defaults={"libelle": lib, "anal1_id": a1, "lettrable": lettrable})
        mizrahi, bit = [], ""
        for i, (nom, fmt) in enumerate(d["banques"][:3], 1):
            code, numero = f"B{i}", ("512000", "512100", "512200")[i - 1]
            compte, _ = Compte.objects.get_or_create(numero=numero, defaults={"libelle": nom.upper()[:100], "anal1_id": "BIL.5"})
            Journal.objects.get_or_create(code=code, defaults={"intitule": nom[:60], "type": "BQ", "compte": compte})
            if fmt == "mizrahi":
                mizrahi.append(code)
            elif fmt == "bit" and not bit:
                bit = code
        if d.get("caisse"):
            compte, _ = Compte.objects.get_or_create(numero="530000", defaults={"libelle": "CAISSE", "anal1_id": "BIL.5"})
            Journal.objects.get_or_create(code="CA", defaults={"intitule": "Caisse", "type": "CA", "compte": compte})
        for code, lib, typ in JOURNAUX:
            Journal.objects.get_or_create(code=code, defaults={"intitule": lib, "type": typ})
        _reglage("releves_mizrahi", ",".join(mizrahi))
        _reglage("releve_bit", bit)
        _reglage("compte_virement", "580000", "Virements internes et paiements par carte")
        _reglage("compte_attente", "470000", "Opérations en attente d'éclaircissement")
        _reglage("compte_report_a_nouveau", "110000", "Compte de report à nouveau (clôture)")
        _reglage("journal_a_nouveaux", "AN", "Journal des à-nouveaux (clôture)")
        from .models import MoyenPaiement
        for i, j in enumerate(Journal.objects.filter(compte__isnull=False).order_by("code")):   # un moyen par banque
            lib = "BIT" if j.code == bit else ("Caisse (espèces)" if j.code == "CA" else j.intitule[:40])
            if MoyenPaiement.objects.filter(libelle=lib).exclude(journal=j).exists():
                lib = f"{lib[:34]} ({j.code})"                # deux banques du même nom
            MoyenPaiement.objects.get_or_create(journal=j, defaults={"libelle": lib, "ordre": i})
        from .saisie import initialiser_parametres
        initialiser_parametres()
        fait += [f"exercice {libelle}", f"{Compte.objects.count()} comptes", f"{Journal.objects.count()} journaux",
                 "codes analytiques et préfixes", "modèles de saisie et moyens de paiement"]
    _reglage("demarrage", "fait", "Assistant de premier démarrage passé")
    _reglage("demarrage_le", dt.date.today().isoformat(), "Date du premier démarrage (début de la période d'essai)")
    Modification.objects.create(auteur=auteur, lot="Démarrage", action="Assistant de premier démarrage",
                                objet=d["nom"][:200], apres=" ; ".join(fait)[:300])
    return fait


def exercice_propose():
    a = dt.date.today().year
    return dt.date(a, 1, 1), dt.date(a, 12, 31)


# ---------------------------------------------------------------- aiguillage

LIBRES = ("/static/", "/demarrage/", "/deconnexion", "/logout", "/admin/logout", "/favicon")


class DemarrageMiddleware:
    """Site sans utilisateur → création de l'administrateur ; base neuve → assistant, à l'arrivée sur le tableau de bord
    (administrateur seulement ; les autres pages restent ouvertes, par exemple pour recharger une sauvegarde)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith(LIBRES):
            if not User.objects.exists():
                return redirect("demarrage_compte")
            u = getattr(request, "user", None)
            if request.path == "/" and u and u.is_authenticated and u.has_perm("compta.parametrer") and a_faire():
                return redirect("demarrage")
        return self.get_response(request)
