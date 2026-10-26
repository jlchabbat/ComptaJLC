"""Fichier des écritures comptables (FEC, article A47 A-1 du livre des procédures fiscales).

Un fichier texte par exercice : 18 colonnes séparées par des tabulations, une ligne par ligne d'écriture,
dates AAAAMMJJ, montants avec la virgule comme séparateur décimal. Nom : <SIREN>FEC<date de clôture>.txt.
Le compte d'un tiers est donné en compte auxiliaire, rattaché au préfixe de son type (411, 401…).
"""

from .models import Ligne
from .reglages import lire

COLONNES = ["JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum", "CompteLib",
            "CompAuxNum", "CompAuxLib", "PieceRef", "PieceDate", "EcritureLib", "Debit", "Credit",
            "EcritureLet", "DateLet", "ValidDate", "Montantdevise", "Idevise"]


def _texte(v):
    """Pas de tabulation ni de retour à la ligne dans une zone."""
    return " ".join(str(v or "").split())


def _date(d):
    return d.strftime("%Y%m%d") if d else ""


def _montant(v):
    return f"{v:.2f}".replace(".", ",")


def nom_fichier(ex):
    siren = "".join(c for c in lire("siren") if c.isdigit())
    return f"{siren if len(siren) == 9 else '000000000'}FEC{_date(ex.fin)}.txt"


def lignes_fec(ex):
    """Lignes de l'exercice, à-nouveaux compris, dans l'ordre chronologique puis des numéros de Mvt."""
    lignes = (Ligne.objects.filter(mouvement__date__range=(ex.debut, ex.fin))
              .select_related("mouvement__journal", "compte__tiers__type")
              .order_by("mouvement__date", "mouvement__numero", "ordre", "pk"))
    for l in lignes:
        m, c = l.mouvement, l.compte
        tiers = getattr(c, "tiers", None)
        if tiers and tiers.type:
            compte_num, compte_lib = tiers.type.prefixe, tiers.type.libelle
            aux_num, aux_lib = c.numero, str(tiers)
        else:
            compte_num, compte_lib, aux_num, aux_lib = c.numero, c.libelle, "", ""
        yield [m.journal_id, m.journal.intitule, m.numero, _date(m.date), compte_num, compte_lib,
               aux_num, aux_lib, m.numero, _date(m.date), l.libelle or m.commentaire,
               _montant(l.debit), _montant(l.credit), l.lettrage, "",
               _date(m.cree_le.date() if m.cree_le else m.date), "", ""]


def contenu(ex):
    rangs = [COLONNES] + list(lignes_fec(ex))
    return "\r\n".join("\t".join(_texte(v) for v in r) for r in rangs) + "\r\n"
