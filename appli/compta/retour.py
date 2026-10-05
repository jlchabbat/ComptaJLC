"""Bouton « ← Retour à la liste » des fiches : l'application retient la dernière adresse (filtres compris) de chaque
liste consultée, et le bouton d'une fiche ramène à la plus récente des listes d'où elle peut s'ouvrir, même après un
ou plusieurs enregistrements sur la fiche."""

import time

from django.urls import reverse

# fiche (nom d'URL) -> listes d'où elle s'ouvre ; la première sert à défaut
LISTES_MOUVEMENT = ["ecritures", "grand_livre", "journaux", "balance", "analytique", "analytique_detail", "membre", "fiche",
                    "rapprochement_journal", "justificatifs_a_classer", "modifications", "controles", "tableau_de_bord"]
LISTES = {
    "mouvement": LISTES_MOUVEMENT, "mouvement_modifier": LISTES_MOUVEMENT, "mouvement_nouveau": LISTES_MOUVEMENT,
    "membre": ["membres", "cotisations", "provisoires", "codes"],
    "fiche": ["fiches"], "fiche_modifier": ["fiches"],
    "utilisateur": ["utilisateurs"],
}
MEMORISEES = {n for noms in LISTES.values() for n in noms}
CLE = "listes_consultees"


class MemoireListesMiddleware:
    """Retient l'adresse complète (filtres compris) de chaque liste affichée."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        reponse = self.get_response(request)
        m = getattr(request, "resolver_match", None)
        if (request.method == "GET" and m and m.url_name in MEMORISEES and reponse.status_code == 200
                and "export" not in request.GET and hasattr(request, "session")
                and reponse.get("Content-Type", "").startswith("text/html")):
            listes = request.session.get(CLE, {})
            listes[m.url_name] = [request.get_full_path(), time.time()]
            request.session[CLE] = listes
        return reponse


def adresse(request, fiche=None, defaut=None):
    """Adresse de retour de la fiche : la plus récente de ses listes consultées, sinon defaut, sinon sa première liste."""
    fiche = fiche or getattr(getattr(request, "resolver_match", None), "url_name", "")
    noms = LISTES.get(fiche, [])
    vues = request.session.get(CLE, {}) if hasattr(request, "session") else {}
    vues = [(vues[n][1], vues[n][0]) for n in noms if n in vues and vues[n][0] != request.get_full_path()]
    if vues:
        return max(vues)[1]
    return defaut or (reverse(noms[0]) if noms else reverse("tableau_de_bord"))


# ---------------------------------------------------------------- bouton « ✕ Fermer » de l'en-tête (toutes les pages)

SANS_FERMER = {"tableau_de_bord", "login", "demarrage", "demarrage_compte"}
PARENTS = {                                   # page -> page d'où elle s'ouvre (mêmes paramètres d'adresse)
    "releve_parametres": "rapprochement_journal", "releve_import": "rapprochement_journal",
    "rapprochement_journal": "rapprochement", "traductions": "rapprochement", "provisoires": "fiches",
    "compte": "plan", "compte_nouveau": "plan", "journal": "journaux_param", "journal_nouveau": "journaux_param",
    "code_axe": "axes_param", "releves_historique": "rapprochement",
    "archive": "cloture", "analytique_detail": "analytique", "situation": "tableau_de_bord", "situation_excel": "situation",
    "etats": "tableau_de_bord", "licence": "tableau_de_bord", "echanges": "tableau_de_bord", "referentiels": "tableau_de_bord",
    "base": "tableau_de_bord", "parametres": "tableau_de_bord", "justificatifs_imprimer": "justificatifs_a_classer",
    "fiche_papier": "fiches", "justificatif_a_classer_voir": "justificatifs_a_classer", "mon_compte": "tableau_de_bord",
}


def adresse_fermer(request):
    """Où mène « Fermer » : la liste d'une fiche, la page d'origine d'une sous-page, sinon le tableau de bord."""
    m = getattr(request, "resolver_match", None)
    nom = m.url_name if m else ""
    if not nom or nom in SANS_FERMER:
        return ""
    if nom in LISTES:
        return adresse(request, nom)
    if nom == "ligne_fiche":
        from .models import LigneFiche
        l = LigneFiche.objects.filter(pk=m.kwargs.get("pk")).first()
        return reverse("fiche", args=[l.fiche_id]) if l else reverse("fiches")
    if nom in PARENTS:
        parent = PARENTS[nom]
        return reverse(parent, kwargs=m.kwargs if parent == "rapprochement_journal" else None)
    return reverse("tableau_de_bord")


def contexte(request):
    try:
        return {"adresse_fermer": adresse_fermer(request)}
    except Exception:                                     # jamais bloquant pour la page
        return {"adresse_fermer": ""}
