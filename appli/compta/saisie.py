"""Saisie guidée : génération des écritures d'une opération, contrôles, enregistrement.

Reprend l'onglet Saisie du classeur (Lot 1) : le type d'opération choisit un
schéma (T_Schemas), qui décrit les lignes générées ; le moyen de paiement
donne le journal et le compte de trésorerie. Conventions des écritures
existantes : une opération avec tiers = un Mvt de 4 lignes dans le journal du
paiement (facture puis règlement), 2 lignes sans règlement (journal VT ou
HA) ; virement interne et paiement Isracard = deux Mvt passant par 580000.
"""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from .models import (
    CodeAnalytique, Compte, Exercice, Journal, Ligne, LigneSchema, ModeleOperation, Modification, MoyenPaiement, Mouvement,
    Reglage, TypeTiers,
)


@dataclass
class Operation:
    date: dt.date | None = None
    modele: ModeleOperation | None = None
    tiers: Compte | None = None
    montant: Decimal | None = None
    paiement: MoyenPaiement | None = None
    vers: MoyenPaiement | None = None
    anal2: CodeAnalytique | None = None
    compte: Compte | None = None
    remboursement: bool = False
    libelle: str = ""


@dataclass
class LigneGeneree:
    mvt: int            # 1 ou 2 (rang dans l'opération)
    journal: Journal | None
    compte: Compte | None
    debit: Decimal
    credit: Decimal


@dataclass
class Resultat:
    lignes: list = field(default_factory=list)
    erreurs: dict = field(default_factory=dict)   # contrôle → message
    libelle: str = ""

    @property
    def ok(self):
        return bool(self.lignes) and not self.erreurs


def libelle(op):
    if op.libelle.strip():
        return op.libelle.strip().upper()
    if not op.modele:
        return ""
    texte = ("REMBOURSEMENT " if op.remboursement else "") + op.modele.libelle_type
    if op.tiers:
        texte += " - " + op.tiers.libelle.upper()
    return texte


def generer(op):
    """Lignes générées par l'opération (sans contrôle)."""
    if not op.modele:
        return []
    regle = bool(op.paiement and op.paiement.regle)
    virement = Compte.objects.filter(numero=Reglage.lire("compte_virement")).first()
    contrepartie = op.compte or op.modele.compte
    res = []
    for ls in op.modele.lignes_schema(regle):
        compte = {"TIERS": op.tiers, "CONTREPARTIE": contrepartie,
                  "TRESO": op.paiement.journal.compte if regle else None,
                  "DEST": op.vers.journal.compte if op.vers and op.vers.regle else None,
                  "VIREMENT": virement}[ls.role]
        journal = {"DEFAUT": op.modele.journal_defaut,
                   "PAIEMENT": op.paiement.journal if regle else None,
                   "DESTINATION": op.vers.journal if op.vers and op.vers.regle else None,
                   "PAIEMENT_OU_DEFAUT": op.paiement.journal if regle else op.modele.journal_defaut}[ls.journal]
        sens = ls.sens if not op.remboursement else ("C" if ls.sens == "D" else "D")
        m = op.montant or Decimal("0")
        res.append(LigneGeneree(ls.mvt, journal, compte, m if sens == "D" else Decimal("0"), m if sens == "C" else Decimal("0")))
    return res


def date_jma(d):
    return f"{d:%d/%m/%Y}"


def controler(op):
    """Les 11 contrôles bloquants de l'onglet Saisie."""
    r = Resultat(lignes=generer(op), libelle=libelle(op))
    e = r.erreurs
    ouvert = Exercice.ouvert()
    if not op.date:
        e["Date"] = "Saisir la date."
    elif Exercice.date_close(op.date):
        e["Date"] = "Date dans un exercice clos."
    elif ouvert and not (ouvert.debut <= op.date <= ouvert.fin):
        e["Date"] = f"Date hors de l'exercice ouvert ({date_jma(ouvert.debut)} au {date_jma(ouvert.fin)})."
    if not op.modele:
        e["Type d'opération"] = "Choisir un type d'opération."
        return r
    if not op.montant or op.montant <= 0:
        e["Montant"] = "Saisir un montant positif ; pour une opération inverse, cocher Remboursement."
    m = op.modele
    if m.tiers is None:
        if op.tiers:
            e["Tiers"] = "Ce type d'opération n'a pas de tiers : vider la case."
    elif not op.tiers:
        e["Tiers"] = f"Choisir le {m.tiers.libelle.lower()}."
    elif not op.tiers.numero.startswith(m.tiers.prefixe):
        e["Tiers"] = f"Ce type d'opération attend un {m.tiers.libelle.lower()} (compte {m.tiers.prefixe}…)."
    if m.paiement_obligatoire and not (op.paiement and op.paiement.regle):
        e["Moyen de paiement"] = "Choisir la banque ou la caisse."
    if m.schema == "VI":
        if not (op.vers and op.vers.regle):
            e["Virement"] = "Choisir le compte qui reçoit le virement."
        elif op.paiement and op.vers.journal_id == op.paiement.journal_id:
            e["Virement"] = "Les deux comptes du virement doivent être différents."
    elif op.vers:
        e["Virement"] = "La case « Vers » ne sert qu'aux virements internes : la vider."
    if not op.anal2:                                      # axe 2 facultatif (comptes 6 et 7 seulement quand il est donné)
        from .reglages import code_axe2_defaut
        defaut = code_axe2_defaut()                       # un seul axe : code d'office
        if defaut:
            op.anal2 = CodeAnalytique.objects.get(code=defaut)
    utilise_contrepartie = LigneSchema.objects.filter(schema=m.schema, role="CONTREPARTIE").exists()
    contrepartie = op.compte or m.compte
    if not utilise_contrepartie:
        if op.compte:
            e["Compte"] = "Ce type d'opération n'utilise pas de compte : vider la case."
    elif not contrepartie:
        e["Compte"] = f"Choisir le compte (classe {m.classe})."
    elif m.classe and not contrepartie.numero.startswith(m.classe):
        e["Compte"] = f"Ce type d'opération attend un compte de classe {m.classe}."
    if contrepartie and contrepartie.projet and not op.anal2 and "Compte" not in e:
        e["Événement / projet (axe 2)"] = f"Le compte {contrepartie.numero} est affecté à un projet : choisir le code axe 2."
    if r.lignes and not e:
        if any(l.compte is None for l in r.lignes):
            e["Écritures générées"] = "Un compte généré est manquant (vérifier les réglages et les moyens de paiement)."
        elif any(l.journal is None for l in r.lignes):
            e["Écritures générées"] = "Un journal généré est manquant (vérifier le modèle d'opération)."
        elif sum(l.debit for l in r.lignes) != sum(l.credit for l in r.lignes):
            e["Équilibre"] = "Écritures déséquilibrées."
    if op.date and op.montant and r.libelle and Ligne.objects.filter(
            mouvement__date=op.date, libelle=r.libelle, debit=op.montant).exists():
        e["Déjà enregistrée ?"] = "Une opération de même date, libellé et montant existe déjà."
    return r


@transaction.atomic
def enregistrer(op, utilisateur, forcer_doublon=False):
    """Crée le ou les mouvements ; refuse si un contrôle bloquant échoue."""
    r = controler(op)
    if forcer_doublon:
        r.erreurs.pop("Déjà enregistrée ?", None)
    if not r.ok:
        raise ValueError("; ".join(r.erreurs.values()))
    numero = Mouvement.prochain_numero()
    crees = []
    for rang in sorted({l.mvt for l in r.lignes}):
        ls = [l for l in r.lignes if l.mvt == rang]
        mv = Mouvement.objects.create(numero=numero + rang - 1, date=op.date, journal=ls[0].journal,
                                      origine="saisie", cree_par=utilisateur)
        Ligne.objects.bulk_create([Ligne(mouvement=mv, ordre=i, compte=l.compte, libelle=r.libelle, debit=l.debit, credit=l.credit,
                                         anal2=op.anal2 if l.compte.porte_axe2 else None) for i, l in enumerate(ls)])
        crees.append(mv)
    Modification.objects.create(auteur=utilisateur.get_username() if utilisateur else "", action="Saisie",
                                objet=", ".join(f"Mvt {m.numero}" for m in crees),
                                apres=f"{op.modele.type} · {r.libelle} · {op.montant}")
    return crees


# ---------------------------------------------------------------- paramètres initiaux (repris du classeur, Lot 1)

TYPES_TIERS = [("Membre", "411"), ("Fournisseur", "401")]
MOYENS = [("Mizrahi compte courant", "B1"), ("Mizrahi épargne", "B2"), ("BIT", "BIT"), ("Caisse (espèces)", "CA"), ("Non réglé", None)]
SCHEMAS = [
    ("RT", 1, 1, "TIERS", "D", False, "PAIEMENT_OU_DEFAUT"), ("RT", 2, 1, "CONTREPARTIE", "C", False, "PAIEMENT_OU_DEFAUT"),
    ("RT", 3, 1, "TRESO", "D", True, "PAIEMENT_OU_DEFAUT"), ("RT", 4, 1, "TIERS", "C", True, "PAIEMENT_OU_DEFAUT"),
    ("DT", 1, 1, "CONTREPARTIE", "D", False, "PAIEMENT_OU_DEFAUT"), ("DT", 2, 1, "TIERS", "C", False, "PAIEMENT_OU_DEFAUT"),
    ("DT", 3, 1, "TIERS", "D", True, "PAIEMENT_OU_DEFAUT"), ("DT", 4, 1, "TRESO", "C", True, "PAIEMENT_OU_DEFAUT"),
    ("RS", 1, 1, "TRESO", "D", False, "PAIEMENT"), ("RS", 2, 1, "CONTREPARTIE", "C", False, "PAIEMENT"),
    ("DS", 1, 1, "CONTREPARTIE", "D", False, "PAIEMENT"), ("DS", 2, 1, "TRESO", "C", False, "PAIEMENT"),
    ("RM", 1, 1, "TRESO", "D", False, "PAIEMENT"), ("RM", 2, 1, "TIERS", "C", False, "PAIEMENT"),
    ("RF", 1, 1, "TIERS", "D", False, "PAIEMENT"), ("RF", 2, 1, "TRESO", "C", False, "PAIEMENT"),
    ("VI", 1, 1, "VIREMENT", "D", False, "PAIEMENT"), ("VI", 2, 1, "TRESO", "C", False, "PAIEMENT"),
    ("VI", 3, 2, "DEST", "D", False, "DESTINATION"), ("VI", 4, 2, "VIREMENT", "C", False, "DESTINATION"),
    ("CB", 1, 1, "CONTREPARTIE", "D", False, "DEFAUT"), ("CB", 2, 1, "VIREMENT", "C", False, "DEFAUT"),
    ("CB", 3, 2, "VIREMENT", "D", False, "PAIEMENT"), ("CB", 4, 2, "TRESO", "C", False, "PAIEMENT"),
]
MODELES = [
    # type, schéma, compte, journal par défaut, tiers, paiement obligatoire, classe, libellé type, aide
    ("Cotisation membre", "RT", "700000", "VT", "Membre", False, "7", "COTISATION",
     "Facture la cotisation au membre ; avec un moyen de paiement, le règlement est passé dans la même opération."),
    ("Facture manifestation (membre)", "RT", "710000", "VT", "Membre", False, "7", "FACTURE MANIFESTATION",
     "Participation d'un membre à une manifestation, réglée ou non."),
    ("Recette d'opération (membre)", "RT", "720000", "VT", "Membre", False, "7", "FACTURE OPERATION",
     "Recette d'une opération facturée à un membre."),
    ("Don reçu d'un membre", "RT", "725000", "VT", "Membre", False, "7", "DON", "Don d'un membre, suivi sur son compte."),
    ("Règlement d'un membre", "RM", None, None, "Membre", True, "", "REGLEMENT", "Encaissement d'une facture déjà passée au membre."),
    ("Don reçu (sans tiers)", "RS", "725000", None, None, True, "7", "DON", "Don encaissé directement, sans compte de membre."),
    ("Subvention", "RS", "740000", None, None, True, "7", "SUBVENTION", "Subvention encaissée."),
    ("Intérêts perçus", "RS", "750000", None, None, True, "7", "INTERETS", "Intérêts versés par la banque."),
    ("Dépense directe", "DS", None, None, None, True, "6", "DEPENSE", "Dépense payée immédiatement : choisir le compte de charge."),
    ("Frais bancaires", "DS", "600100", None, None, True, "6", "FRAIS BANCAIRES", "Frais prélevés par la banque."),
    ("Facture fournisseur", "DT", None, "HA", "Fournisseur", False, "6", "FACTURE FOURNISSEUR",
     "Facture d'un fournisseur, réglée ou non : choisir le compte de charge."),
    ("Règlement fournisseur", "RF", None, None, "Fournisseur", True, "", "REGLEMENT FOURNISSEUR",
     "Paiement d'une facture fournisseur déjà passée."),
    ("Virement interne", "VI", None, None, None, True, "", "VIREMENT INTERNE",
     "Virement entre deux comptes de l'association : choisir le compte qui reçoit dans « Vers »."),
    ("Paiement carte {carte}", "CB", "600000", "OD", None, True, "6", "CARTE {CARTE}",
     "Charge contre 580000, puis prélèvement 580000 contre la banque (décision Q2)."),
]


def initialiser_parametres():
    """Crée les paramètres de saisie absents (idempotent) ; ignore ceux dont un compte ou journal manque."""
    for lib, pref in TYPES_TIERS:
        TypeTiers.objects.get_or_create(libelle=lib, defaults={"prefixe": pref})
    for s, n, mvt, role, sens, si_regle, jr in SCHEMAS:
        LigneSchema.objects.get_or_create(schema=s, ligne=n, defaults=dict(mvt=mvt, role=role, sens=sens, si_regle=si_regle, journal=jr))
    from .reglages import journaux, lire
    mizrahi, bit, carte = journaux("releves_mizrahi"), journaux("releve_bit"), lire("carte_bancaire")
    for i, (lib, jnl) in enumerate(MOYENS):
        if jnl == "BIT":                                  # journal du relevé Bit, s'il y en a un
            if not bit:
                continue
            jnl = bit[0]
        elif jnl in ("B1", "B2") and jnl not in mizrahi:  # banque sans relevé Mizrahi : nom du journal
            j = Journal.objects.filter(code=jnl).first()
            if not j or MoyenPaiement.objects.filter(journal=j).exists():
                continue
            lib = j.intitule
        if jnl is None or Journal.objects.filter(code=jnl).exists():
            MoyenPaiement.objects.get_or_create(libelle=lib, defaults={"journal_id": jnl, "ordre": i})
    for i, (t, s, compte, jnl, tiers, oblig, classe, lib, aide) in enumerate(MODELES):
        if "{carte}" in t:                                # paiement par carte : seulement si le site en a une
            if not carte:
                continue
            t, lib = t.format(carte=carte), lib.format(CARTE=carte.upper())
        if (compte and not Compte.objects.filter(numero=compte).exists()) or (jnl and not Journal.objects.filter(code=jnl).exists()):
            continue
        ModeleOperation.objects.get_or_create(type=t, defaults=dict(
            schema=s, compte_id=compte, journal_defaut_id=jnl, tiers=TypeTiers.objects.filter(libelle=tiers).first(),
            paiement_obligatoire=oblig, classe=classe, libelle_type=lib, aide=aide, ordre=i))
    from .fiches import initialiser as initialiser_fiches
    initialiser_fiches()
    if Compte.objects.filter(numero="700000").exists():
        Reglage.objects.get_or_create(cle="compte_cotisations", defaults={
            "valeur": "700000", "description": "Compte des cotisations (suivi des membres)"})
    from .membres import creer_manquants
    creer_manquants()
