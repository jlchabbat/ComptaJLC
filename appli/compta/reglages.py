"""Réglages propres à chaque association (un site par association) : nom, devise, formats de relevés bancaires,
carte de paiement, hébergeur des justificatifs en lien, traductions du relevé.

Ils sont enregistrés dans Reglage (Administration › Paramètres, fichier Parametres.xlsx). Un réglage absent prend
la valeur neutre d'une nouvelle association ; la migration 0016 a donné aux sites existants les valeurs de la Loge."""

from .models import Reglage

# clé, description, valeur neutre (nouvelle association), valeur des sites existants (Loge)
REGLAGES = [
    ("nom_association", "Nom de l'association (en-tête des pages, situation, éditions)", "", "Loge Bnei Brith"),
    ("devise", "Symbole de la devise des montants (₪, €, $…)", "€", "₪"),
    ("releves_mizrahi", "Journaux dont le relevé PDF est au format Mizrahi-Tefahot (hébreu), séparés par des virgules ; "
                        "vide : relevés en Excel ou CSV seulement", "", "B1,B2"),
    ("releve_bit", "Journal du relevé Bit (format imposé, remplace le précédent) ; vide : pas de Bit", "", "B3"),
    ("carte_bancaire", "Nom de la carte de paiement réglée par la banque le mois suivant (passe par le compte de "
                       "virement interne) ; vide : pas de carte", "", "Isracard"),
    ("hebergeur_liens", "Site qui héberge des justificatifs gardés en lien (ex. SUMIT) ; vide : pas de lien", "", "SUMIT"),
    ("traductions_releve", "Traduire les libellés du relevé (hébreu → français) : oui ou non", "non", "oui"),
    ("un_seul_axe", "Un seul axe analytique (axe 1, nature) : oui ou non ; l'axe 2 est alors masqué et chaque ligne "
                    "reçoit d'office le code axe2_defaut", "non", "non"),
    ("axe2_defaut", "Code axe 2 mis d'office quand il n'y a qu'un axe (créé au besoin)", "GEN", "GEN"),
]
NEUTRES = {cle: neutre for cle, _, neutre, _ in REGLAGES}


def lire(cle):
    return Reglage.lire(cle, NEUTRES.get(cle, "")).strip()


def journaux(cle):
    """Liste de codes de journaux d'un réglage (« B1,B2 » → ["B1", "B2"])."""
    return [c.strip().upper() for c in lire(cle).replace(";", ",").split(",") if c.strip()]


def oui(cle):
    return lire(cle).lower() in ("oui", "o", "1", "vrai", "yes")


def un_seul_axe():
    return oui("un_seul_axe")


def code_axe2_defaut():
    """Code axe 2 d'office (un seul axe) : créé au besoin ; None si le site a deux axes."""
    if not un_seul_axe():
        return None
    from .models import CodeAnalytique
    code = lire("axe2_defaut") or "GEN"
    CodeAnalytique.objects.get_or_create(code=code, defaults={"axe": 2, "libelle": "Général"})
    return code


def devise():
    return lire("devise")


def montant(v):
    """1234.5 → « 1 234,50 ₪ » (avec la devise du site)."""
    texte = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return f"{texte} {devise()}".rstrip()


def contexte(request):
    """Processeur de contexte : nom de l'association, devise et options, dans tous les gabarits."""
    try:
        return {"association": lire("nom_association"), "devise": devise(), "avec_traductions": oui("traductions_releve"),
                "hebergeur_liens": lire("hebergeur_liens"), "deux_axes": not un_seul_axe()}
    except Exception:                                    # base pas encore créée (première migration)
        return {"association": "", "devise": NEUTRES["devise"], "avec_traductions": False, "hebergeur_liens": "",
                "deux_axes": True}
