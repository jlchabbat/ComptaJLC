"""TVA : montant à déclarer à une date et écriture de liquidation.

Les soldes sont cumulés (depuis les derniers à-nouveaux, sinon depuis la première écriture) jusqu'à la date de fin de la
période déclarée : une période non liquidée reste due à la suivante. La liquidation solde les comptes de TVA
collectée et déductible ainsi que le crédit reporté, et porte le net au compte de TVA à décaisser (ou au
crédit à reporter). Les comptes viennent des réglages (préfixes 4457 et 4456, comptes 44551 et 44567).
"""

from django.db import transaction
from django.db.models import Sum

from . import etats
from .models import ZERO, Compte, Exercice, Journal, Ligne, Modification, Mouvement, arrondi
from .reglages import lire


def _soldes(lignes, prefixe):
    """[(compte, solde débit − crédit)] des comptes de ce préfixe, soldes nuls exclus."""
    if not prefixe:
        return []
    rows = (lignes.filter(compte__numero__startswith=prefixe).values("compte").annotate(d=Sum("debit"), c=Sum("credit"))
            .order_by("compte"))
    comptes = Compte.objects.in_bulk([r["compte"] for r in rows])
    return [(comptes[r["compte"]], arrondi(r["d"] - r["c"])) for r in rows if arrondi(r["d"] - r["c"])]


def declaration(debut, fin):
    lignes = etats.lignes_cumulees(fin)
    collectee = [(c, -s) for c, s in _soldes(lignes, lire("tva_collectee"))]
    credit = Compte.objects.filter(pk=lire("compte_credit_tva")).first()
    # Le crédit à reporter (44567) relève aussi de la classe 4456 : il est compté à part.
    deductible = [(c, s) for c, s in _soldes(lignes, lire("tva_deductible")) if c != credit]
    report = etats.solde_cumule(credit, fin) if credit else ZERO
    total_c = sum((s for _, s in collectee), ZERO)
    total_d = sum((s for _, s in deductible), ZERO)
    net = total_c - total_d - report
    ventes = Ligne.objects.filter(mouvement__date__range=(debut, fin), compte__numero__startswith="70").aggregate(
        d=Sum("debit"), c=Sum("credit"))
    return {"debut": debut, "fin": fin, "collectee": collectee, "deductible": deductible, "report": report,
            "total_collectee": total_c, "total_deductible": total_d, "net": net,
            "a_payer": max(net, ZERO), "credit": max(-net, ZERO),
            "chiffre_affaires": arrondi(ventes["c"]) - arrondi(ventes["d"]),
            "a_liquider": bool(collectee or deductible)}


def _ligne(mv, ordre, compte, libelle, solde):
    """Ligne qui solde le compte : solde débiteur → crédit, et inversement."""
    return Ligne.objects.create(mouvement=mv, ordre=ordre, compte=compte, libelle=libelle,
                                debit=-solde if solde < 0 else ZERO, credit=solde if solde > 0 else ZERO)


@transaction.atomic
def liquider(debut, fin, utilisateur=None):
    d = declaration(debut, fin)
    if not d["a_liquider"]:
        raise ValueError("Rien à liquider : les comptes de TVA collectée et déductible sont soldés.")
    if Exercice.date_close(fin):
        raise ValueError("La date de fin est dans un exercice clos.")
    journal = Journal.objects.filter(pk=lire("journal_tva")).first()
    a_payer = Compte.objects.filter(pk=lire("compte_tva_a_payer")).first()
    credit = Compte.objects.filter(pk=lire("compte_credit_tva")).first()
    manquants = [nom for nom, o in (("journal " + lire("journal_tva"), journal), ("compte " + lire("compte_tva_a_payer"), a_payer),
                                    ("compte " + lire("compte_credit_tva"), credit)) if o is None]
    if manquants:
        raise ValueError("À créer avant la liquidation : " + ", ".join(manquants) + " (ou à changer dans les réglages).")
    libelle = f"TVA du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"
    mv = Mouvement.objects.create(numero=Mouvement.prochain_numero(), date=fin, journal=journal, origine="saisie",
                                  cree_par=utilisateur, commentaire=f"Liquidation de la {libelle}")
    ordre = 0
    for compte, s in d["collectee"]:
        ordre += 1
        _ligne(mv, ordre, compte, libelle, -s)
    for compte, s in d["deductible"]:
        ordre += 1
        _ligne(mv, ordre, compte, libelle, s)
    if d["report"]:
        ordre += 1
        _ligne(mv, ordre, credit, libelle, d["report"])
    if d["net"]:
        _ligne(mv, ordre + 1, a_payer if d["net"] > 0 else credit, libelle, d["net"])
    Modification.objects.create(auteur=utilisateur.get_username() if utilisateur else "", lot="TVA",
                                action="Liquidation de la TVA", objet=f"Mvt {mv.numero}",
                                apres=f"{libelle} ; net {d['net']}")
    return mv
