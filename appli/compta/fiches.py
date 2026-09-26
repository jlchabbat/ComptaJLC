"""Fiches bénévoles : contrôle des lignes, écritures générées, report en comptabilité.

Conventions reprises du fichier de liaison Excel (docs/fichier-liaison.md) :

| Cas                               | Écritures (un Mvt, journal du mode de paiement)          |
|-----------------------------------|----------------------------------------------------------|
| Recette d'un membre payée         | membre D / produit C + trésorerie D / membre C           |
| Recette d'un membre non payée     | membre D / produit C : reste dû par le membre            |
| Recette d'un autre payeur         | trésorerie D / produit C                                 |
| Dépense payée (carte : 580000)    | charge D / trésorerie C                                  |
| Dépense avancée par un membre     | charge D / membre C : dette envers le membre             |
| Gestion                           | trésorerie D / compte C (reçu) ; compte D / trésorerie C |
"""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from .models import ZERO, Compte, Exercice, Journal, Ligne, ModeFiche, Modification, Mouvement, NatureFiche


@dataclass
class Ecriture:
    compte: Compte | None
    debit: Decimal
    credit: Decimal


@dataclass
class Resultat:
    journal: Journal | None = None
    lignes: list = field(default_factory=list)
    erreurs: dict = field(default_factory=dict)
    libelle: str = ""

    @property
    def ok(self):
        return bool(self.lignes) and not self.erreurs


def libelle(l):
    texte = l.nature.libelle_ecriture if l.nature_id else ""
    if l.qui:
        texte += " - " + l.qui
    return texte.upper()[:200]


def anal2(l):
    return l.fiche.anal2 if l.fiche.type == "activite" else l.anal2


def generer(l):
    """Écritures d'une ligne de fiche (sans contrôle) : [(compte, sens)] puis montants."""
    if not (l.nature_id and l.mode_id):
        return None, []
    contre, mode, membre = l.compte or l.nature.compte, l.mode, l.membre
    if l.fiche.type == "gestion":
        membre = None       # gestion : l'argent passe directement par la trésorerie
    treso = mode.compte
    if l.sens == "R":
        if mode.genre == "NON_PAYE":
            schema = [(membre, "D"), (contre, "C")]
        elif mode.genre == "TRESO" and membre:
            schema = [(membre, "D"), (contre, "C"), (treso, "D"), (membre, "C")]
        elif mode.genre == "TRESO":
            schema = [(treso, "D"), (contre, "C")]
        else:
            return mode.journal, []
    else:
        if mode.genre == "AVANCE":
            schema = [(contre, "D"), (membre, "C")]
        elif mode.genre == "TRESO":
            schema = [(contre, "D"), (treso, "C")]
        else:
            return mode.journal, []
    m = l.montant or ZERO
    return mode.journal, [Ecriture(c, m if s == "D" else ZERO, m if s == "C" else ZERO) for c, s in schema]


def controler(l):
    journal, lignes = generer(l)
    r = Resultat(journal=journal, lignes=lignes, libelle=libelle(l) if l.nature_id else "")
    e = r.erreurs
    ouvert = Exercice.ouvert()
    if not l.date:
        e["Date"] = "Saisir la date."
    elif Exercice.date_close(l.date):
        e["Date"] = "Date dans un exercice clos."
    elif ouvert and not (ouvert.debut <= l.date <= ouvert.fin):
        e["Date"] = "Date hors de l'exercice ouvert."
    if not l.montant or l.montant <= 0:
        e["Montant"] = "Saisir un montant positif."
    if not l.nature_id:
        e["Nature"] = "Choisir la nature."
    elif (l.nature.type_fiche, l.nature.sens) != (l.fiche.type, l.sens):
        e["Nature"] = "Cette nature ne correspond pas à la ligne (recette ou dépense)."
    if not l.mode_id:
        e["Mode de paiement"] = ("À compléter par le trésorier." if l.fiche.type == "gestion" else "Choisir le mode de paiement.")
    elif l.mode.type_fiche != l.fiche.type or l.mode.sens not in ("*", l.sens):
        e["Mode de paiement"] = "Ce mode ne convient pas à cette ligne."
    elif l.fiche.type == "activite" and l.mode.genre in ("NON_PAYE", "AVANCE") and not l.membre:
        e["Mode de paiement"] = f"« {l.mode.libelle} » demande un membre."
    if l.provisoire_id and not l.provisoire.compte_id:
        e["Tiers"] = "Tiers provisoire : compte à attribuer par le trésorier."
    if not anal2(l):
        e["Axe 2"] = ("Le trésorier doit fixer le code axe 2 de la fiche." if l.fiche.type == "activite"
                      else "Code axe 2 à choisir par le trésorier.")
    if not e and (not lignes or any(x.compte is None for x in lignes)):
        e["Écritures générées"] = "Un compte généré est manquant (vérifier les modes de paiement)."
    return r


def totaux(fiche):
    ls = list(fiche.lignes.all())
    recettes = sum((l.montant for l in ls if l.sens == "R"), ZERO)
    depenses = sum((l.montant for l in ls if l.sens == "D"), ZERO)
    return {"participants": sum(l.personnes or 0 for l in ls if l.sens == "R"), "recettes": recettes, "depenses": depenses,
            "resultat": recettes - depenses}


@transaction.atomic
def reporter(fiche, utilisateur):
    """Crée un mouvement par ligne non encore reportée ; refuse tout si une ligne est signalée."""
    a_reporter = list(fiche.lignes.filter(mouvement__isnull=True).select_related("nature", "mode", "fiche"))
    resultats = [(l, controler(l)) for l in a_reporter]
    signalees = [(l, r) for l, r in resultats if not r.ok]
    if signalees:
        raise ValueError(f"{len(signalees)} ligne(s) à corriger avant le report.")
    numero, piece = Mouvement.prochain_numero(), Mouvement.prochaine_piece()
    crees = []
    for i, (l, r) in enumerate(resultats):
        mv = Mouvement.objects.create(numero=numero + i, date=l.date, journal=r.journal, piece=piece + i, origine="liaison",
                                      cree_par=utilisateur, commentaire=f"Fiche bénévole « {fiche.titre} » (ligne {l.pk})")
        Ligne.objects.bulk_create([Ligne(mouvement=mv, ordre=k, compte=x.compte, libelle=r.libelle, debit=x.debit, credit=x.credit,
                                         anal2=anal2(l)) for k, x in enumerate(r.lignes)])
        l.mouvement = mv
        l.save(update_fields=["mouvement"])
        crees.append(mv)
    fiche.statut = "reportee"
    fiche.save(update_fields=["statut"])
    if crees:
        Modification.objects.create(auteur=utilisateur.get_username(), action="Report fiche", objet=f"fiche {fiche.pk} {fiche.titre}"[:200],
                                    apres=f"Mvt {crees[0].numero} à {crees[-1].numero}")
    return crees


# ---------------------------------------------------------------- paramètres initiaux (repris du fichier de liaison)

NATURES = [
    # fiche, sens, libellé, compte, libellé d'écriture
    ("activite", "R", "Participation", "710000", "PARTICIPATION"), ("activite", "R", "Don", "725000", "DON"),
    ("activite", "R", "Sponsor / subvention", "740000", "SUBVENTION"), ("activite", "R", "Autre recette", "720000", "RECETTE"),
    ("activite", "D", "Manifestation (traiteur, artiste, matériel…)", "610000", "DEPENSE"),
    ("activite", "D", "Location de salle", "600200", "SALLE"), ("activite", "D", "Frais divers", "600000", "FRAIS DIVERS"),
    ("gestion", "R", "Don reçu", "725000", "DON RECU"), ("gestion", "R", "Aide reçue", "740000", "AIDE RECUE"),
    ("gestion", "R", "Autre recette", "720000", "RECETTE"),
    ("gestion", "D", "Don versé", "625000", "DON VERSE"), ("gestion", "D", "Aide versée", "630000", "AIDE VERSEE"),
    ("gestion", "D", "Autre dépense", "600000", "DEPENSE"),
]
MODES = [
    # fiche, sens (* = les deux), libellé, genre, journal, compte (vide : compte de virement interne pour la carte)
    ("activite", "*", "Espèces", "TRESO", "CA", "530000"), ("activite", "*", "Chèque", "TRESO", "B1", "512000"),
    ("activite", "*", "Virement", "TRESO", "B1", "512000"), ("activite", "*", "Bit", "TRESO", "B3", "512200"),
    ("activite", "R", "Non payé", "NON_PAYE", "VT", None), ("activite", "D", "Carte Isracard", "TRESO", "OD", "VIREMENT"),
    ("activite", "D", "Avance d'un membre", "AVANCE", "OD", None),
    ("gestion", "*", "Virement Mizrahi", "TRESO", "B1", "512000"), ("gestion", "*", "Virement BIT", "TRESO", "B3", "512200"),
    ("gestion", "*", "Espèces", "TRESO", "CA", "530000"),
]


def initialiser():
    """Crée les natures et modes absents (idempotent) ; ignore ceux dont le compte ou le journal manque."""
    from .models import Reglage
    for i, (t, s, lib, compte, lib_e) in enumerate(NATURES):
        if Compte.objects.filter(numero=compte).exists():
            NatureFiche.objects.get_or_create(type_fiche=t, sens=s, libelle=lib,
                                              defaults={"compte_id": compte, "libelle_ecriture": lib_e, "ordre": i})
    for i, (t, s, lib, genre, jnl, compte) in enumerate(MODES):
        if compte == "VIREMENT":
            compte = Reglage.lire("compte_virement") or None
            if not compte:
                continue
        if not Journal.objects.filter(code=jnl).exists() or (compte and not Compte.objects.filter(numero=compte).exists()):
            continue
        ModeFiche.objects.get_or_create(type_fiche=t, sens=s, libelle=lib,
                                        defaults={"genre": genre, "journal_id": jnl, "compte_id": compte, "ordre": i})
