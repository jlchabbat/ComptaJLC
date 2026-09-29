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
