"""Imports et exports par fichiers Excel : un fichier .xlsx par nature de données, de même structure à l'import
et à l'export.

Les fichiers à importer (référentiels, écritures, relevés bancaires) se déposent dans <dossier ComptaBB>/Imports ;
après un import réussi, ils sont déplacés et datés dans Imports/Importés. Les exports s'écrivent dans
<dossier ComptaBB>/Exports. Un import est tout ou rien : à la première ligne en erreur, rien n'est enregistré.
"""

import datetime as dt
import io
import shutil
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import openpyxl
from django.db import transaction

from . import dossiers, export, releves
from .membres import ENTETES_MODELE, importer_tableau
from .models import (ZERO, Budget, CodeAnalytique, Compte, Exercice, Journal, Ligne, LigneFiche, LigneReleve, Membre,
                     Modification, Mouvement, Prefixe, Rapprochement, Reglage, Traduction)

IMPORTES = "Importés"


# ---------------------------------------------------------------- dossiers

REGLAGES_DOSSIERS = {c: (c.split("_")[1].capitalize(), lib) for c, lib in dossiers.REGLAGES.items()}


def defaut(cle):
    return dossiers.defaut(cle)


def imports():
    return dossiers.imports()


def exports():
    return dossiers.exports()


def _cree(d):
    d.mkdir(parents=True, exist_ok=True)
    return d


def importes():
    return _cree(imports() / IMPORTES)


def changer_dossiers(valeurs, auteur=""):
    """Enregistre les chemins des dossiers Imports, Exports et Sauvegardes (vide = dossier par défaut) ; les crée au besoin."""
    erreurs = []
    for cle, v in valeurs.items():
        v = (v or "").strip().strip('"')
        if v:
            if not dossiers.valable(v):
                erreurs.append(f"{v} : chemin complet du site attendu (par exemple /home/ComptaBB/comptabb-data/Exports), "
                               "ou vide pour le dossier par défaut.")
                continue
            try:
                _cree(Path(v))
            except OSError as e:
                erreurs.append(f"{v} : dossier impossible à créer ({e.strerror or e}).")
                continue
        avant = Reglage.lire(cle)
        if v != avant:
            Reglage.objects.update_or_create(cle=cle, defaults={"valeur": v, "description": REGLAGES_DOSSIERS[cle][1]})
            Modification.objects.create(auteur=auteur, lot="Échanges", action="Paramètre", objet=cle, avant=avant, apres=v)
    if erreurs:
        raise Refus(erreurs)


def tout_exporter(auteur=""):
    """Jeu complet : un fichier par format, Parametres.xlsx (classeur complet) et une sauvegarde de la base.

    Renvoie (fichiers écrits, sauvegarde)."""
    from . import base_donnees
    from . import parametres as prm
    ecrits = [exporter(f, auteur)[0] for f in FORMATS]
    chemin = exports() / f"Parametres_{dt.datetime.now():%Y-%m-%d_%H%M%S}.xlsx"
    chemin.write_bytes(prm.contenu_classeur())
    ecrits.append(chemin)
    ecrire_lexiques()
    sauvegarde = base_donnees.sauvegarder("export")
    Modification.objects.create(auteur=auteur, lot="Échanges", action="Tout exporter et sauvegarder", objet=str(exports())[:200],
                                apres=f"{len(ecrits)} fichiers ; sauvegarde {sauvegarde.name}")
    return ecrits, sauvegarde


# ---------------------------------------------------------------- lecture des cellules

class Refus(Exception):
    """Import refusé : liste des erreurs (ligne Excel et motif)."""

    def __init__(self, erreurs):
        super().__init__(f"{len(erreurs)} erreur(s)")
        self.erreurs = erreurs


class Lecteur:
    """Convertit les cellules d'une ligne et note les erreurs sans s'arrêter."""

    def __init__(self):
        self.erreurs = []

    def erreur(self, n, texte):
        self.erreurs.append(f"Ligne {n} : {texte}")

    def texte(self, n, d, col, obligatoire=False, longueur=None):
        v = d.get(col)
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        s = "" if v is None else str(v).strip()
        if obligatoire and not s:
            self.erreur(n, f"{col} manquant.")
        if longueur and len(s) > longueur:
            self.erreur(n, f"{col} : {longueur} caractères au plus.")
        return s

    def date(self, n, d, col, obligatoire=True):
        v = d.get(col)
        if v in (None, ""):
            if obligatoire:
                self.erreur(n, f"{col} manquante.")
            return None
        r = releves.date(v)
        if r is None:
            self.erreur(n, f"{col} « {v} » n'est pas une date.")
        return r

    def montant(self, n, d, col, obligatoire=False):
        v = d.get(col)
        if v in (None, ""):
            if obligatoire:
                self.erreur(n, f"{col} manquant.")
            return None
        r = releves.nombre(v)
        if r is None:
            self.erreur(n, f"{col} « {v} » n'est pas un montant.")
        return r

    def entier(self, n, d, col, permis, defaut=None):
        v = d.get(col)
        if v in (None, ""):
            if defaut is None:
                self.erreur(n, f"{col} manquant.")
            return defaut
        try:
            r = int(float(v))
        except (TypeError, ValueError):
            r = None
        if r not in permis:
            self.erreur(n, f"{col} : {' ou '.join(map(str, permis))} attendu.")
        return r

    def oui(self, n, d, col, defaut=False):
        v = d.get(col)
        s = "" if v is None else str(v).strip().lower()
        if s == "":
            return defaut
        if s in ("oui", "o", "1", "x", "true", "vrai"):
            return True
        if s in ("non", "n", "0", "false", "faux"):
            return False
        self.erreur(n, f"{col} : oui ou non attendu.")
        return defaut

    def verifier(self):
        if self.erreurs:
            raise Refus(self.erreurs)


def oui_non(v):
    return "oui" if v else "non"


# ---------------------------------------------------------------- formats

def _sans_accent(texte):
    import unicodedata
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


@dataclass
class Format:
    nom: str                 # nom du fichier, sans extension ni date
    contenu: str
    colonnes: list
    exporter: object         # () -> lignes
    importer: object         # (lignes [(n° de ligne Excel, {colonne: valeur})], fichier, utilisateur) -> résumé
    montants: tuple = ()     # colonnes (1 = A) au format montant
    facultatives: tuple = ()  # dernières colonnes, absentes des fichiers plus anciens
    libres: bool = False      # colonnes supplémentaires libres (une par axe de comptes)
    alias: tuple = ()         # autres débuts de nom de fichier reconnus
    synonymes: tuple = ()     # autres en-têtes acceptés, dans le même ordre (autres noms de colonnes acceptés)

    def entetes(self):
        if self.libres:
            from .models import AxeCompte
            return self.colonnes + list(AxeCompte.objects.values_list("nom", flat=True))
        return self.colonnes

    def reconnait(self, chemin):
        debut = _sans_accent(Path(chemin).stem.split("_")[0].strip())          # « Libellés_… » = Libelles
        return debut == self.nom.lower() or debut.lstrip("0123456789") in (self.nom.lower(),) + self.alias


def _egal(a, b):
    """Valeur du site et valeur du fichier identiques (nombres et textes de même sens, vide = vide)."""
    if a in (None, "") and b in (None, ""):
        return True
    try:
        return a == b or str(a).strip() == str(b).strip() or (isinstance(a, (int, float, Decimal)) and Decimal(str(a)) == Decimal(str(b)))
    except (InvalidOperation, ValueError):
        return False


def maj_ou_cree(modele, cles, valeurs, compteur):
    """Crée l'élément absent ; met à jour celui dont le fichier change une valeur ; laisse tel quel (inchangé) celui qui est
    identique : un fichier réimporté n'ajoute aucun doublon et ne signale que les vraies modifications."""
    actuel = modele.objects.filter(**cles).first()
    if actuel is None:
        modele.objects.create(**cles, **valeurs)
        compteur["créé(s)"] += 1
    elif all(_egal(getattr(actuel, k), v) for k, v in valeurs.items()):
        compteur["inchangé(s)"] += 1
    else:
        for k, v in valeurs.items():
            setattr(actuel, k, v)
        actuel.save()
        compteur["mis à jour"] += 1


def resume(compteur):
    return ", ".join(f"{v} {k}" for k, v in compteur.items() if v) or "aucune ligne"


# ---- exercices

def exp_exercices():
    return [[e.libelle, e.debut, e.fin, oui_non(e.clos)] for e in Exercice.objects.all()]


def imp_exercices(lignes, fichier, utilisateur=None):
    L, a_faire = Lecteur(), []
    for n, d in lignes:
        lib, debut, fin = L.texte(n, d, "Libellé", True, 40), L.date(n, d, "Début"), L.date(n, d, "Fin")
        L.oui(n, d, "Clos")
        if debut and fin and debut > fin:
            L.erreur(n, "le début est après la fin.")
        ex = Exercice.objects.filter(libelle=lib).first()
        if ex and ex.clos and (ex.debut, ex.fin) != (debut, fin):
            L.erreur(n, f"l'exercice {lib} est clos : ses dates ne changent plus.")
        a_faire.append((lib, debut, fin))
    L.verifier()
    c = defaultdict(int)
    for lib, debut, fin in a_faire:
        maj_ou_cree(Exercice, {"libelle": lib}, {"debut": debut, "fin": fin}, c)
    return resume(c) + " (la colonne Clos est indicative : la clôture se fait par Fin d'exercice › Clôture)"


# ---- paramètres

def exp_parametres():
    """Tous les réglages enregistrés, plus ceux de l'association encore absents (avec leur valeur neutre)."""
    from .reglages import REGLAGES
    lignes = {r.cle: [r.cle, r.valeur, r.description] for r in Reglage.objects.all()}
    for cle, description, neutre, _ in REGLAGES:
        lignes.setdefault(cle, [cle, neutre, description])
    return [lignes[c] for c in sorted(lignes)]


def imp_parametres(lignes, fichier, utilisateur=None):
    L, a_faire = Lecteur(), []
    for n, d in lignes:
        a_faire.append((L.texte(n, d, "Clé", True, 40), L.texte(n, d, "Valeur", longueur=200), L.texte(n, d, "Description", longueur=200)))
    L.verifier()
    c = defaultdict(int)
    for cle, valeur, description in a_faire:
        maj_ou_cree(Reglage, {"cle": cle}, {"valeur": valeur, "description": description}, c)
    return resume(c)


# ---- axes analytiques et préfixes

def exp_axe(axe):
    def f():
        return [[x.code, x.libelle] + ([x.statut] if axe == 2 else []) for x in CodeAnalytique.objects.filter(axe=axe)]
    return f


def imp_axe(axe):
    def f(lignes, fichier, utilisateur=None):
        L, a_faire = Lecteur(), []
        for n, d in lignes:
            code = L.texte(n, d, "Code", True, 20)
            lib = L.texte(n, d, "Libellé", longueur=100)
            statut = L.entier(n, d, "Statut", (0, 1, 2), defaut=1) if axe == 2 else 1
            autre = CodeAnalytique.objects.filter(code=code).exclude(axe=axe).first()
            if autre:
                L.erreur(n, f"le code {code} existe déjà sur l'axe {autre.axe}.")
            a_faire.append((code, lib, statut))
        L.verifier()
        c = defaultdict(int)
        for code, lib, statut in a_faire:
            valeurs = {"axe": axe, "libelle": lib} | ({"statut": statut} if axe == 2 else {})
            maj_ou_cree(CodeAnalytique, {"code": code}, valeurs, c)
        return resume(c)
    return f


def exp_prefixes():
    return [[p.prefixe, p.axe, p.libelle] for p in Prefixe.objects.all()]


def imp_prefixes(lignes, fichier, utilisateur=None):
    L, a_faire = Lecteur(), []
    for n, d in lignes:
        a_faire.append((L.texte(n, d, "Préfixe", True, 10), L.entier(n, d, "Axe", (1, 2)), L.texte(n, d, "Libellé", longueur=60)))
    L.verifier()
    c = defaultdict(int)
    for prefixe, axe, lib in a_faire:
        maj_ou_cree(Prefixe, {"prefixe": prefixe}, {"axe": axe, "libelle": lib}, c)
    return resume(c)


# ---- plan comptable et journaux

def exp_plan():
    return [[x.numero, x.libelle, x.anal1_id or "", oui_non(x.lettrable), oui_non(x.actif)] for x in Compte.objects.all()]


def imp_plan(lignes, fichier, utilisateur=None):
    L, a_faire = Lecteur(), []
    axe1 = set(CodeAnalytique.objects.filter(axe=1).values_list("code", flat=True))
    for n, d in lignes:
        numero, lib, anal1 = L.texte(n, d, "Compte", True, 20), L.texte(n, d, "Libellé", True, 100), L.texte(n, d, "Axe 1")
        if anal1 and anal1 not in axe1:
            L.erreur(n, f"code axe 1 « {anal1} » inconnu (importer d'abord Axe1.xlsx).")
        a_faire.append((numero, {"libelle": lib, "anal1_id": anal1 or None, "lettrable": L.oui(n, d, "Lettrable"),
                                 "actif": L.oui(n, d, "Actif", True)}))
    L.verifier()
    c = defaultdict(int)
    for numero, valeurs in a_faire:
        maj_ou_cree(Compte, {"numero": numero}, valeurs, c)
    from .membres import creer_manquants
    fiches = creer_manquants()                            # une fiche pour chaque nouveau compte de tiers (401…, 411…)
    return resume(c) + (f" ; {fiches} fiche(s) tiers créée(s)" if fiches else "")


def exp_journaux():
    return [[j.code, j.intitule, j.type, j.compte_id or "", oui_non(j.actif)] for j in Journal.objects.all()]


def imp_journaux(lignes, fichier, utilisateur=None):
    L, a_faire = Lecteur(), []
    comptes = set(Compte.objects.values_list("numero", flat=True))
    for n, d in lignes:
        code, intitule = L.texte(n, d, "Code", True, 10), L.texte(n, d, "Intitulé", True, 60)
        compte = L.texte(n, d, "Compte de trésorerie")
        if compte and compte not in comptes:
            L.erreur(n, f"compte {compte} inconnu (importer d'abord PlanComptable.xlsx).")
        valeurs = {"intitule": intitule, "type": L.texte(n, d, "Type", longueur=10), "compte_id": compte or None,
                   "actif": L.oui(n, d, "Actif", True)}
        a_faire.append((code, valeurs))
    L.verifier()
    c = defaultdict(int)
    for code, valeurs in a_faire:
        maj_ou_cree(Journal, {"code": code}, valeurs, c)
    return resume(c)


# ---- tiers (même moteur que la fiche tiers)

def exp_tiers():
    return [[m.compte_id, m.type.libelle if m.type_id else "", m.nom, m.prenom, m.adresse, m.code_postal, m.ville, m.telephone,
             m.email, m.date_adhesion, m.get_statut_display() if m.type_id and m.type.libelle == "Membre" else "", m.cotisation]
            for m in Membre.objects.select_related("type").order_by("compte")]


def imp_tiers(lignes, fichier, utilisateur=None):
    r = importer_tableau([ENTETES_MODELE] + [[d.get(c) for c in ENTETES_MODELE] for _, d in lignes])
    if r.erreurs:
        raise Refus(r.erreurs)
    return f"{len(r.crees)} créé(s), {len(r.mis_a_jour)} mis à jour"


# ---- axes de comptes (colonnes libres)

def exp_axes_comptes():
    from .models import AxeCompte, ValeurCompte
    axes = list(AxeCompte.objects.values_list("nom", flat=True))
    vals = defaultdict(dict)
    for v in ValeurCompte.objects.select_related("axe"):
        vals[v.compte_id][v.axe.nom] = v.valeur
    return [[c] + [vals[c].get(a, "") for a in axes] for c in sorted(vals)]


def imp_axes_comptes(lignes, fichier, utilisateur=None):
    """Une colonne par axe (son en-tête est le nom de l'axe) ; une cellule vide ne remplace rien ; rien n'est supprimé."""
    from .models import AxeCompte, ValeurCompte
    L, a_faire = Lecteur(), []
    comptes = set(Compte.objects.values_list("numero", flat=True))
    for n, d in lignes:
        numero = L.texte(n, d, "Compte", True, 20)
        if numero and numero not in comptes:
            L.erreur(n, f"compte {numero} inconnu (importer d'abord PlanComptable.xlsx).")
        for axe, v in d.items():
            if axe != "Compte" and v not in (None, ""):
                a_faire.append((numero, axe[:40], str(v).strip()[:100]))
    L.verifier()
    c = defaultdict(int)
    for i, nom in enumerate(dict.fromkeys(a for _, a, _ in a_faire)):
        AxeCompte.objects.get_or_create(nom=nom, defaults={"ordre": i})
    axes = {a.nom: a for a in AxeCompte.objects.all()}
    for numero, axe, v in a_faire:
        maj_ou_cree(ValeurCompte, {"compte_id": numero, "axe": axes[axe]}, {"valeur": v}, c)
    return resume(c)


# ---- liens des documents en ligne

def exp_liens():
    from .models import Justificatif
    return [[j.mouvement.numero, j.lien, j.description] for j in Justificatif.objects.exclude(lien="").select_related("mouvement")]


def imp_liens(lignes, fichier, utilisateur=None):
    from . import justificatifs as just
    from .models import Justificatif
    L, a_faire = Lecteur(), []
    for n, d in lignes:
        numero, lien = L.entier(n, d, "Mvt", range(1, 10 ** 9)), L.texte(n, d, "Lien", True, 500)
        m = Mouvement.objects.filter(numero=numero).first() if numero else None
        if numero and not m:
            L.erreur(n, f"Mvt {numero} inconnu (importer d'abord Ecritures.xlsx).")
        if lien and not lien.startswith("https://"):
            L.erreur(n, "adresse https:// attendue.")
        a_faire.append((m, lien, L.texte(n, d, "Description", longueur=150)))
    L.verifier()
    auteur = utilisateur.get_username() if utilisateur else ""
    c = defaultdict(int)
    for m, lien, description in a_faire:
        deja = (Justificatif.objects.filter(lien=lien).exists()               # encore en ligne, ou déjà copié sur le site
                or Modification.objects.filter(action="Document en ligne enregistré sur le site", avant=lien[:300]).exists())
        if deja:
            c["déjà joint(s)"] += 1
            continue
        just.ajouter_lien(m, lien, "Document en ligne", description, auteur, rapatrier_aussitot=False)
        c["joint(s)"] += 1
    return resume(c)


# ---- traductions des relevés

def exp_traductions():
    return [[t.hebreu, t.traduction] for t in Traduction.objects.all()]


def imp_traductions(lignes, fichier, utilisateur=None):
    L, a_faire = Lecteur(), []
    for n, d in lignes:
        a_faire.append((L.texte(n, d, "Opération (hébreu)", True, 120), L.texte(n, d, "Traduction", True, 120)))
    L.verifier()
    c = defaultdict(int)
    for hebreu, traduction in a_faire:
        maj_ou_cree(Traduction, {"cle": Traduction.cle_de(hebreu)}, {"hebreu": hebreu, "traduction": traduction}, c)
    return resume(c)


# ---- budget

def exp_budget():
    return [[b.exercice.libelle, b.get_nature_display(), b.compte_id or "", b.anal1_id or "", b.anal2_id or "", b.montant]
            for b in Budget.objects.select_related("exercice")]


def imp_budget(lignes, fichier, utilisateur=None):
    L, a_faire = Lecteur(), []
    natures = {"charges": "C", "c": "C", "produits": "P", "p": "P"}
    for n, d in lignes:
        lib = L.texte(n, d, "Exercice", True)
        ex = Exercice.objects.filter(libelle=lib).first()
        if lib and not ex:
            L.erreur(n, f"exercice « {lib} » inconnu.")
        nature = natures.get(L.texte(n, d, "Nature").lower())
        if not nature:
            L.erreur(n, "Nature : Charges ou Produits attendu.")
        compte, anal1, anal2 = L.texte(n, d, "Compte"), L.texte(n, d, "Axe 1"), L.texte(n, d, "Axe 2")
        if len([x for x in (compte, anal1, anal2) if x]) != 1:
            L.erreur(n, "remplir un seul des trois : Compte, Axe 1 ou Axe 2.")
        if compte and not Compte.objects.filter(numero=compte).exists():
            L.erreur(n, f"compte {compte} inconnu.")
        for code, axe in ((anal1, 1), (anal2, 2)):
            if code and not CodeAnalytique.objects.filter(code=code, axe=axe).exists():
                L.erreur(n, f"code axe {axe} « {code} » inconnu.")
        a_faire.append(({"exercice": ex, "nature": nature, "compte_id": compte or None, "anal1_id": anal1 or None,
                         "anal2_id": anal2 or None}, L.montant(n, d, "Montant", True)))
    L.verifier()
    c = defaultdict(int)
    for cles, montant in a_faire:
        maj_ou_cree(Budget, cles, {"montant": montant}, c)
    return resume(c)


# ---- écritures

def exp_ecritures():
    return [[l.mouvement.date, l.mouvement.journal_id, l.mouvement.numero, l.compte_id, l.libelle,
             l.debit or None, l.credit or None, l.anal2_id, l.lettrage]
            for l in Ligne.objects.select_related("mouvement").order_by("mouvement__numero", "ordre")]


def empreinte(date, journal, lignes):
    """Ce qui fait qu'un Mvt est le même, quels que soient son numéro et ses libellés."""
    return date, journal, tuple(sorted((compte, Decimal(debit or 0), Decimal(credit or 0)) for compte, debit, credit in lignes))


def imp_ecritures(lignes, fichier, utilisateur=None):
    """Mvt nouveau : créé. Mvt existant modifié dans le fichier : mis à jour (tracé, comme une correction, et listé dans le
    compte rendu) ; identique : ignoré. Un Mvt absent du fichier n'est jamais supprimé. Un Mvt nouveau identique à un Mvt
    du site (même date, journal, comptes et montants, autre numéro) est un doublon : il est écarté et signalé, pas importé."""
    from . import corrections
    L, mvts = Lecteur(), defaultdict(list)
    comptes = set(Compte.objects.values_list("numero", flat=True))
    journaux = set(Journal.objects.values_list("code", flat=True))
    axe2 = set(CodeAnalytique.objects.filter(axe=2).values_list("code", flat=True))
    existants = set(Mouvement.objects.values_list("numero", flat=True))
    from .reglages import code_axe2_defaut
    defaut2 = code_axe2_defaut()                          # un seul axe : Anal2 facultatif, code d'office
    if defaut2:
        axe2.add(defaut2)
    for n, d in lignes:
        date, jnl = L.date(n, d, "Date"), L.texte(n, d, "Jnl", True)
        numero = L.entier(n, d, "Mvt", range(1, 10 ** 9))
        compte, anal2 = L.texte(n, d, "Compte", True), L.texte(n, d, "Anal2", not defaut2) or defaut2
        debit, credit = L.montant(n, d, "Débit") or ZERO, L.montant(n, d, "Crédit") or ZERO
        if jnl and jnl not in journaux:
            L.erreur(n, f"journal {jnl} inconnu.")
        if compte and compte not in comptes:
            L.erreur(n, f"compte {compte} inconnu.")
        if anal2 and anal2 not in axe2:
            L.erreur(n, f"code axe 2 « {anal2} » inconnu.")
        if (debit > 0) == (credit > 0) or debit < 0 or credit < 0:
            L.erreur(n, "un débit OU un crédit, positif (RG-03).")
        mvts[numero].append((n, date, jnl, compte, L.texte(n, d, "Libellé", True, 200), debit, credit, anal2,
                             L.texte(n, d, "Let", longueur=10)))
    for numero, ls in mvts.items():
        if numero is None:
            continue
        if len({(x[1], x[2]) for x in ls}) > 1:
            L.erreur(ls[0][0], f"Mvt {numero} : même date et même journal attendus sur toutes ses lignes.")
        td, tc = sum((x[5] for x in ls), ZERO), sum((x[6] for x in ls), ZERO)
        if td != tc:
            L.erreur(ls[0][0], f"Mvt {numero} déséquilibré : débit {td} ≠ crédit {tc} (RG-01).")
    en_base = defaultdict(list)                  # empreinte (date, journal, comptes et montants) -> n° des Mvt du site
    for m in Mouvement.objects.prefetch_related("lignes"):
        en_base[empreinte(m.date, m.journal_id, [(l.compte_id, l.debit, l.credit) for l in m.lignes.all()])].append(m.numero)
    modifies, ecartes = {}, {}
    for numero, ls in mvts.items():
        m = Mouvement.objects.filter(numero=numero).first() if numero in existants else None
        if not m and numero is not None:
            doublons = en_base.get(empreinte(ls[0][1], ls[0][2], [(x[3], x[5], x[6]) for x in ls]))
            if doublons:                                  # déjà en compta sous un autre numéro : écarté, pas créé en double
                ecartes[numero] = doublons[0]
                continue
        if not m:
            if ls[0][1] and ls[0][2] != "AN" and Exercice.date_close(ls[0][1]):
                L.erreur(ls[0][0], f"Mvt {numero} : date dans un exercice clos (RG-04).")
            continue
        actuel = [(m.date, m.journal_id, l.compte_id, l.libelle, l.debit, l.credit, l.anal2_id, l.lettrage)
                  for l in m.lignes.all()]
        if actuel != [tuple(x[1:]) for x in ls]:
            if corrections.verrou(m):
                L.erreur(ls[0][0], f"Mvt {numero} modifié dans le fichier, mais non modifiable : {corrections.verrou(m)}")
            modifies[numero] = m
    L.verifier()
    crees = 0
    for numero, ls in sorted(mvts.items()):
        _, date, jnl = ls[0][:3]
        if numero in ecartes:
            continue
        if numero in modifies:
            m = modifies[numero]
            ids = list(m.lignes.values_list("pk", flat=True)) + [None] * len(ls)    # même rang = même ligne (pointage gardé)
            corrections.modifier(m, date, Journal.objects.get(code=jnl),
                                 [corrections.LigneSaisie(ids[i], Compte.objects.get(numero=x[3]), x[4], x[5], x[6],
                                                          CodeAnalytique.objects.get(code=x[7])) for i, x in enumerate(ls)],
                                 f"import {fichier}", utilisateur)
            for l, x in zip(m.lignes.all(), ls):
                if l.lettrage != x[8]:
                    Ligne.objects.filter(pk=l.pk).update(lettrage=x[8])
        elif numero not in existants:
            m = Mouvement.objects.create(numero=numero, date=date, journal_id=jnl, origine="import",
                                         commentaire=f"Import {fichier}", cree_par=utilisateur)
            Ligne.objects.bulk_create([Ligne(mouvement=m, ordre=i, compte_id=x[3], libelle=x[4], debit=x[5], credit=x[6],
                                             anal2_id=x[7], lettrage=x[8]) for i, x in enumerate(ls)])
            crees += 1
    texte = f"{crees} mouvement(s) ajouté(s), {len(modifies)} modifié(s), {len(mvts) - crees - len(modifies) - len(ecartes)} inchangé(s)"
    if modifies:
        texte += " (modifiés : Mvt " + ", ".join(map(str, sorted(modifies)[:20])) + (" …" if len(modifies) > 20 else "") + ")"
    if ecartes:
        texte += (f" ; {len(ecartes)} doublon(s) écarté(s), déjà en compta sous un autre numéro (Mvt "
                  + ", ".join(f"{n} = {v}" for n, v in sorted(ecartes.items())[:20]) + (" …" if len(ecartes) > 20 else "") + ")")
    return texte


def imp_libelles(lignes, fichier, utilisateur=None):
    """Libellés seulement. Chaque Mvt du fichier est retrouvé sur le site par son contenu (date, journal, comptes et
    montants), pas par son numéro : un fichier venu d'une autre base (numéros décalés) convient. Seuls les libellés
    changent ; montants, comptes, dates, pointages et lettrages ne bougent pas. Mvt introuvable, ambigu ou dans un
    exercice clos : laissé tel quel et signalé."""
    L, mvts = Lecteur(), defaultdict(list)
    for n, d in lignes:
        numero = L.entier(n, d, "Mvt", range(1, 10 ** 9))
        mvts[numero].append((n, L.date(n, d, "Date"), L.texte(n, d, "Jnl", True), L.texte(n, d, "Compte", True),
                             L.texte(n, d, "Libellé", longueur=200) or "", L.montant(n, d, "Débit") or ZERO,
                             L.montant(n, d, "Crédit") or ZERO))
    L.verifier()
    en_base = defaultdict(list)
    for m in Mouvement.objects.prefetch_related("lignes"):
        en_base[empreinte(m.date, m.journal_id, [(l.compte_id, l.debit, l.credit) for l in m.lignes.all()])].append(m)
    faits, identiques, introuvables, ambigus, clos, vus, ecarts = 0, 0, [], [], [], set(), []
    for numero, ls in sorted(mvts.items(), key=lambda x: x[0] or 0):
        if numero is None:
            continue
        candidats = en_base.get(empreinte(ls[0][1], ls[0][2], [(x[3], x[5], x[6]) for x in ls]), [])
        if len(candidats) > 1:                        # plusieurs Mvt identiques : le même numéro départage
            candidats = [m for m in candidats if m.numero == numero] or candidats
        if not candidats:
            introuvables.append(numero)
            ecarts.append((numero, ls))
            continue
        if len(candidats) > 1:
            ambigus.append(f"{numero} (site : " + ", ".join(str(m.numero) for m in candidats) + ")")
            continue
        m = candidats[0]
        if m.pk in vus:                               # deux Mvt du fichier pour un seul du site
            ambigus.append(f"{numero} (site : {m.numero}, déjà pris)")
            continue
        vus.add(m.pk)
        restantes = list(ls)                          # chaque ligne du site reçoit le libellé de la ligne de même compte et montant
        changements = []
        for l in m.lignes.all():
            x = next(x for x in restantes if (x[3], x[5], x[6]) == (l.compte_id, l.debit, l.credit))
            restantes.remove(x)
            if x[4] != l.libelle:
                changements.append((l, x[4]))
        if not changements:
            identiques += 1
            continue
        if Exercice.date_close(m.date):
            clos.append(m.numero)
            continue
        for l, libelle in changements:
            Ligne.objects.filter(pk=l.pk).update(libelle=libelle)
        Modification.objects.create(auteur=utilisateur.get_username() if utilisateur else "", lot="Échanges",
                                    action="Libellés mis à jour", objet=f"Mvt {m.numero} (fichier : Mvt {numero})",
                                    avant=" | ".join(l.libelle for l, _ in changements)[:300],
                                    apres=" | ".join(v for _, v in changements)[:300])
        faits += 1

    def liste(ns):
        return ", ".join(map(str, ns[:30])) + (" …" if len(ns) > 30 else "")
    resume = [f"{faits} mouvement(s) : libellés mis à jour", f"{identiques} déjà à jour"]
    if clos:
        resume.append(f"{len(clos)} dans un exercice clos, non modifié(s) (Mvt du site {liste(clos)})")
    if introuvables:
        resume.append(f"{len(introuvables)} introuvable(s) sur le site (date, journal, comptes ou montants différents ; "
                      f"Mvt du fichier {liste(introuvables)})")
    if ambigus:
        resume.append(f"{len(ambigus)} ambigu(s), non modifié(s) : Mvt du fichier {liste(ambigus)}")
    if ecarts:
        chemin = rapport_ecarts(ecarts, vus)
        resume.append(f"détail des introuvables et mouvement le plus proche sur le site : {chemin.name} "
                      "(Imports / Exports › Télécharger)")
    return " ; ".join(resume)


def _decrire(lignes):
    """« 512000 D 450,00 | 600100 C 450,00 » : comptes et montants d'un Mvt."""
    return " | ".join(f"{c} {'D' if d else 'C'} {(d or cr):.2f}".replace(".", ",") for c, d, cr in sorted(lignes))


def plus_proche(date, journal, lignes, deja_pris=()):
    """Mvt du site le plus ressemblant (date à 10 jours près) et les différences, ou (None, "")."""
    import datetime as dt
    total = sum((d for _, d, _ in lignes), ZERO)
    fichier = {(c, d, cr) for c, d, cr in lignes}
    meilleur, score_max = None, 0
    for m in Mouvement.objects.filter(date__range=(date - dt.timedelta(days=10), date + dt.timedelta(days=10))
                                      ).prefetch_related("lignes"):
        site = {(l.compte_id, l.debit, l.credit) for l in m.lignes.all()}
        score = (3 if m.date == date else 0) + (2 if m.journal_id == journal else 0) + 2 * len(fichier & site) \
            + len({c for c, _, _ in fichier} & {c for c, _, _ in site}) + (2 if m.total_debit == total else 0) \
            - abs((m.date - date).days) * 0.2 - (1 if m.pk in deja_pris else 0)
        if score > score_max:
            meilleur, score_max = m, score
    if not meilleur or score_max < 3:
        return None, "aucun mouvement ressemblant sur le site (à 10 jours près) : absent du site ?"
    m = meilleur
    site = [(l.compte_id, l.debit, l.credit) for l in m.lignes.all()]
    diff = []
    if m.date != date:
        diff.append(f"date {date:%d/%m/%Y} → {m.date:%d/%m/%Y}")
    if m.journal_id != journal:
        diff.append(f"journal {journal} → {m.journal_id}")
    montant_f = max((d or cr for _, d, cr in lignes), default=ZERO)          # montant de l'opération (plus grande ligne)
    montant_s = max((d or cr for _, d, cr in site), default=ZERO)
    if montant_f != montant_s:
        diff.append(f"montant {montant_f:.2f} → {montant_s:.2f}".replace(".", ","))
    comptes_f, comptes_s = {c for c, _, _ in lignes}, {c for c, _, _ in site}
    if comptes_f != comptes_s:
        diff.append("comptes " + ", ".join(sorted(comptes_f - comptes_s)) + " → " + ", ".join(sorted(comptes_s - comptes_f)))
    inverses = sorted({c for c, d, cr in lignes if (c, cr, d) in set(site) and (c, d, cr) not in set(site)})
    if inverses:
        diff.append("sens inversé (débit ↔ crédit) sur " + ", ".join(inverses))
    if not diff:
        diff.append("répartition des lignes différente")
    if m.pk in deja_pris:
        diff.append("ce Mvt du site a déjà reçu les libellés d'un autre Mvt du fichier")
    return m, " ; ".join(diff)


def rapport_ecarts(ecarts, deja_pris=()):
    """Exports/Ecarts_libelles_<date>.xlsx : Mvt du fichier introuvables, Mvt du site le plus proche, différences."""
    import datetime as dt
    lignes = []
    for numero, ls in ecarts:
        date, jnl = ls[0][1], ls[0][2]
        detail = [(x[3], x[5], x[6]) for x in ls]
        m, diff = plus_proche(date, jnl, detail, deja_pris)
        lignes.append([numero, date, jnl, _decrire(detail), " | ".join(dict.fromkeys(x[4] for x in ls if x[4])),
                       m.numero if m else None, m.date if m else None, m.journal_id if m else None,
                       _decrire([(l.compte_id, l.debit, l.credit) for l in m.lignes.all()]) if m else "",
                       " | ".join(dict.fromkeys(l.libelle for l in m.lignes.all())) if m else "", diff])
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = export.feuille(wb, "Introuvables", ["Mvt fichier", "Date fichier", "Jnl fichier", "Comptes et montants (fichier)",
                                             "Libellé du fichier", "Mvt site proposé", "Date site", "Jnl site",
                                             "Comptes et montants (site)", "Libellé actuel (site)", "Différences"], lignes)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, (dt.date, dt.datetime)):
                c.number_format = "DD/MM/YYYY"
    for col, largeur in zip("ABCDEFGHIJK", (10, 12, 8, 45, 45, 10, 12, 8, 45, 45, 60)):
        ws.column_dimensions[col].width = largeur
    ws.freeze_panes = "A2"
    chemin = exports() / f"Ecarts_libelles_{dt.datetime.now():%Y-%m-%d_%H%M}.xlsx"
    wb.save(chemin)
    return chemin


# ---- relevés Banque 1 et Banque 2 (Excel, CSV ou PDF converti) et caisse

COLONNES_BANQUE = ["Date", "Référence", "Opération", "Montant", "Solde"]


def journal_obligatoire(code):
    j = Journal.objects.filter(code=code).first()
    if not j:
        raise Refus([f"Le journal {code} n'existe pas (importer d'abord Journaux.xlsx)."])
    return j


def exp_banque(code):
    def f():
        return [[l.date, l.reference, l.operation, l.montant, l.solde]
                for l in LigneReleve.objects.filter(journal_id=code, ouverture=False)]
    return f


def imp_banque(code):
    def f(lignes, fichier, utilisateur=None):
        journal = journal_obligatoire(code)
        L, a_faire = Lecteur(), []
        for n, d in lignes:
            montant = L.montant(n, d, "Montant", True)
            if montant == 0:
                L.erreur(n, "montant nul.")
            a_faire.append({"date": L.date(n, d, "Date"), "reference": L.texte(n, d, "Référence", longueur=40),
                            "operation": L.texte(n, d, "Opération", longueur=200), "montant": montant,
                            "solde": L.montant(n, d, "Solde")})
        L.verifier()
        try:
            ajoutees, doublons, ecarts = releves.importer(journal, a_faire, source=fichier)
        except ValueError as e:
            raise Refus([str(e)])
        return (f"{ajoutees} ligne(s) ajoutée(s), {doublons} déjà présente(s)"
                + (f" ; attention : {ecarts} solde(s) du relevé incohérent(s)" if ecarts else ""))
    return f


# ---- Bit : format imposé, journal du réglage releve_bit (B3 à la Loge), remplace le relevé existant

def journal_bit():
    from .reglages import journaux
    codes = journaux("releve_bit")
    return codes[0] if codes else ""


def exp_bit():
    code = journal_bit()
    return [[code, l.date, l.operation, l.montant if l.montant > 0 else None, -l.montant if l.montant < 0 else None]
            for l in LigneReleve.objects.filter(journal_id=code, ouverture=False)] if code else []


def imp_bit(lignes, fichier, utilisateur=None):
    code = journal_bit()
    if not code:
        raise Refus(["Relevé Bit non utilisé par cette association (Paramètres : réglage releve_bit vide)."])
    journal = journal_obligatoire(code)
    L, a_faire = Lecteur(), []
    for n, d in lignes:
        jnl = L.texte(n, d, "Journ")
        if jnl != code:
            L.erreur(n, f"journal « {jnl} » : {code} attendu.")
        debit, credit = L.montant(n, d, "Debit"), L.montant(n, d, "Credit")
        if (debit is None) == (credit is None) or (debit or credit or ZERO) <= 0:
            L.erreur(n, "un seul montant, Debit OU Credit, positif.")
        a_faire.append((L.date(n, d, "Date"), L.texte(n, d, "Libelle", True, 50), (debit or ZERO) - (credit or ZERO)))
    L.verifier()
    anciennes = LigneReleve.objects.filter(journal=journal, ouverture=False)
    for r in {l.rapprochement for l in anciennes.select_related("rapprochement") if l.rapprochement_id}:
        releves.depointer(r)
    supprimees = anciennes.count()
    anciennes.delete()
    if a_faire and not LigneReleve.objects.filter(journal=journal, ouverture=True).exists():
        LigneReleve.objects.create(journal=journal, date=min(x[0] for x in a_faire) - dt.timedelta(days=1), rang=0,
                                   operation="Solde d'ouverture", montant=ZERO, solde=ZERO, ouverture=True, source=fichier)
    rangs = defaultdict(int)
    nouvelles = []
    for date, libelle, montant in sorted(a_faire, key=lambda x: x[0]):
        rangs[date] += 1
        nouvelles.append(LigneReleve(journal=journal, date=date, rang=rangs[date], operation=libelle, montant=montant,
                                     source=fichier[:120]))
    LigneReleve.objects.bulk_create(nouvelles)
    return f"{len(nouvelles)} ligne(s) importée(s), {supprimees} ancienne(s) remplacée(s)"


# ---------------------------------------------------------------- catalogue, dans l'ordre d'import

FORMATS = [
    Format("Exercices", "Exercices comptables", ["Libellé", "Début", "Fin", "Clos"], exp_exercices, imp_exercices),
    Format("Reglages", "Réglages (clé, valeur)", ["Clé", "Valeur", "Description"], exp_parametres, imp_parametres),
    Format("Axe1", "Codes analytiques axe 1 (nature)", ["Code", "Libellé"], exp_axe(1), imp_axe(1)),
    Format("Axe2", "Codes analytiques axe 2 (événement, projet)", ["Code", "Libellé", "Statut"], exp_axe(2), imp_axe(2)),
    Format("Prefixes", "Préfixes des codes analytiques", ["Préfixe", "Axe", "Libellé"], exp_prefixes, imp_prefixes),
    Format("PlanComptable", "Plan comptable", ["Compte", "Libellé", "Axe 1", "Lettrable", "Actif"], exp_plan, imp_plan),
    Format("AxesComptes", "Axes de comptes (rubriques, catégories, groupes…), une colonne par axe", ["Compte"],
           exp_axes_comptes, imp_axes_comptes, libres=True),
    Format("Journaux", "Journaux", ["Code", "Intitulé", "Type", "Compte de trésorerie", "Actif"], exp_journaux,
           imp_journaux),
    Format("Tiers", "Tiers : membres, fournisseurs…", ENTETES_MODELE, exp_tiers, imp_tiers, (12,)),
    Format("Traductions", "Traductions des relevés (hébreu)", ["Opération (hébreu)", "Traduction"], exp_traductions, imp_traductions,
           synonymes=(("Libellé hébreu", "Traduction"),)),
    Format("Budget", "Budget", ["Exercice", "Nature", "Compte", "Axe 1", "Axe 2", "Montant"], exp_budget, imp_budget, (6,)),
    Format("Ecritures", "Écritures (Mvt ajoutés ou modifiés)",
           ["Date", "Jnl", "Mvt", "Compte", "Libellé", "Débit", "Crédit", "Anal2", "Let"], exp_ecritures,
           imp_ecritures, (6, 7)),
    Format("Libelles", "Libellés des écritures seulement (Mvt retrouvés par leur contenu)",
           ["Date", "Jnl", "Mvt", "Compte", "Libellé", "Débit", "Crédit", "Anal2", "Let"], exp_ecritures,
           imp_libelles, (6, 7)),
    Format("Liens", "Liens des documents en ligne, joints à leur Mvt", ["Mvt", "Lien", "Description"], exp_liens, imp_liens),
    Format("Banque1", "Relevé Banque 1 (journal B1)", COLONNES_BANQUE, exp_banque("B1"), imp_banque("B1"), (4, 5)),
    Format("Banque2", "Relevé Banque 2 (journal B2)", COLONNES_BANQUE, exp_banque("B2"), imp_banque("B2"), (4, 5)),
    Format("Bit", "Relevé Bit (journal du réglage releve_bit, remplace le précédent)", ["Journ", "Date", "Libelle", "Debit", "Credit"],
           exp_bit, imp_bit, (4, 5)),
    Format("Caisse", "Caisse (journal CA)", COLONNES_BANQUE, exp_banque("CA"), imp_banque("CA"), (4, 5)),
]

PAR_NOM = {f.nom: f for f in FORMATS}


# ---------------------------------------------------------------- lexique (Lexique.xlsx dans Imports et Exports)

LEXIQUE = "Lexique"
O, F = "oui", ""
DATE, MONTANT, TEXTE, CODE, OUI = "date jj/mm/aaaa", "montant (nombre, sans symbole)", "texte", "code (texte)", "oui / non"
REGLES = [
    ("Format", "Un fichier .xlsx par nature de données ; une seule feuille ; ligne 1 = exactement les en-têtes ; données dès la ligne 2."),
    ("Nom du fichier", "Commence par le nom du format : Tiers.xlsx, Tiers_2026-09-27.xlsx… Les exports portent la date du jour."),
    ("Aller-retour", "Un fichier exporté (dossier Exports) se réimporte tel quel : le copier dans le dossier Imports."),
    ("Tout ou rien", "À la moindre erreur, rien n'est enregistré ; la page Imports / Exports liste les lignes en erreur."),
    ("Sécurité", "Une sauvegarde de la base est faite avant chaque import ; le fichier importé est rangé, daté, dans Imports\\Importés."),
    ("Ordre", "Importer dans l'ordre du lexique : chaque fichier ne cite que des codes définis par les précédents."),
    ("Dates", "Dates Excel (affichées jj/mm/aaaa)."),
    ("Montants", "Nombres, sans symbole monétaire ; cellule vide quand il n'y a pas de montant."),
    ("Relevés PDF", "Un relevé PDF déposé dans Imports se convertit en Banque1 ou Banque2 (bouton de la page), à vérifier puis importer."),
]
AIDE = {
    "Exercices": ("Mise à jour par libellé ; un exercice clos ne change plus. La clôture se fait par Fin d'exercice › Clôture.", {
        "Libellé": (O, TEXTE, "Nom de l'exercice (ex. 2026)"), "Début": (O, DATE, "Premier jour"), "Fin": (O, DATE, "Dernier jour"),
        "Clos": (F, OUI, "Indicatif (non modifié par l'import)")}),
    "Reglages": ("Mise à jour par clé.", {
        "Clé": (O, CODE, "Nom du réglage (compte_virement, tolerance_rapprochement, dossier_imports…)"),
        "Valeur": (F, TEXTE, "Valeur du réglage"), "Description": (F, TEXTE, "Explication")}),
    "Axe1": ("Mise à jour par code.", {"Code": (O, CODE, "Code nature (ex. COT.2)"), "Libellé": (F, TEXTE, "Libellé du code")}),
    "Axe2": ("Mise à jour par code.", {"Code": (O, CODE, "Code événement ou projet (ex. MAN.013)"), "Libellé": (F, TEXTE, "Libellé du code"),
                                     "Statut": (F, "0, 1 ou 2", "0 non affecté, 1 en cours (par défaut), 2 terminé")}),
    "Prefixes": ("Mise à jour par préfixe.", {"Préfixe": (O, CODE, "Début des codes (ex. MAN.)"), "Axe": (O, "1 ou 2", "Axe concerné"),
                                             "Libellé": (F, TEXTE, "Libellé du préfixe")}),
    "PlanComptable": ("Mise à jour par numéro de compte ; rien n'est supprimé.", {
        "Compte": (O, CODE, "Numéro de compte (ex. 512000, 411TAIEB001)"), "Libellé": (O, TEXTE, "Intitulé du compte"),
        "Axe 1": (F, CODE, "Code axe 1 du compte (Axe1.xlsx)"), "Lettrable": (F, OUI, "Compte de tiers lettrable (non par défaut)"),
        "Actif": (F, OUI, "Utilisable en saisie (oui par défaut)")}),
    "AxesComptes": ("Une ligne par compte, une colonne par axe (l'en-tête est le nom de l'axe, créé au besoin) ; une cellule vide ne remplace rien.", {
        "Compte": (O, CODE, "Compte (PlanComptable.xlsx)")}),
    "Journaux": ("Mise à jour par code.", {
        "Code": (O, CODE, "B1, B2, B3, CA, OD, VT, HA, AN…"), "Intitulé": (O, TEXTE, "Nom du journal"), "Type": (F, TEXTE, "Type libre (BQ, CA…)"),
        "Compte de trésorerie": (F, CODE, "Compte 5xx des journaux de banque et de caisse (PlanComptable.xlsx)"),
        "Actif": (F, OUI, "Utilisable (oui par défaut)")}),
    "Tiers": ("Tiers retrouvé par compte, sinon par type + nom + prénom ; une cellule vide ne remplace rien ; rien n'est supprimé.", {
        "Compte": (F, CODE, "Compte du tiers ; vide = créé d'après le type (411 + 5 lettres du nom + rang)"),
        "Type": (F, TEXTE, "Membre (par défaut), Fournisseur…"), "Nom": (O, TEXTE, "Nom ou raison sociale"), "Prénom": (F, TEXTE, ""),
        "Adresse": (F, TEXTE, ""), "Code postal": (F, TEXTE, ""), "Ville": (F, TEXTE, ""), "Téléphone": (F, TEXTE, ""),
        "E-mail": (F, TEXTE, "Adresse e-mail valide"), "Date d'adhésion": (F, DATE, "Membres"),
        "Statut": (F, "Actif / Honoraire / Démissionnaire", "Membres"), "Cotisation annuelle": (F, MONTANT, "Cotisation attendue")}),
    "Traductions": ("Mise à jour par opération.", {"Opération (hébreu)": (O, TEXTE, "Libellé du relevé bancaire"),
                                                   "Traduction": (O, TEXTE, "Traduction française")}),
    "Budget": ("Mise à jour par exercice + nature + cible.", {
        "Exercice": (O, TEXTE, "Libellé de l'exercice (Exercices.xlsx)"), "Nature": (O, "Charges / Produits", ""),
        "Compte": (F, CODE, "Cible : un compte…"), "Axe 1": (F, CODE, "… ou un code axe 1…"), "Axe 2": (F, CODE, "… ou un code axe 2 (une seule cible)"),
        "Montant": (O, MONTANT, "Montant budgété")}),
    "Ecritures": ("Le n° de Mvt désigne l'écriture : n° présent sur le site = Mvt mis à jour (tracé), n° nouveau = Mvt ajouté ; un Mvt nouveau identique à un Mvt du site (même date, journal, comptes et montants) est refusé comme doublon. Chaque Mvt équilibré, hors exercice clos.", {
        "Date": (O, DATE, "Même date sur toutes les lignes du Mvt"), "Jnl": (O, CODE, "Journal (Journaux.xlsx)"),
        "Mvt": (O, "entier", "N° de mouvement (une opération équilibrée)"),
        "Compte": (O, CODE, "Compte (PlanComptable.xlsx)"), "Libellé": (O, TEXTE, ""), "Débit": (F, MONTANT, "Débit OU crédit"),
        "Crédit": (F, MONTANT, "Débit OU crédit"), "Anal2": (O, CODE, "Code axe 2 (Axe2.xlsx) ; facultatif avec un seul axe (réglage un_seul_axe)"),
        "Let": (F, TEXTE, "Code de lettrage")}),
    "Liens": ("Chaque lien est joint comme justificatif au Mvt indiqué ; un lien déjà joint est ignoré ; rien n'est supprimé. "
              "Les documents se copient ensuite sur le site (Justificatifs existants › Les enregistrer sur le site).", {
        "Mvt": (O, "entier", "N° du mouvement (Ecritures.xlsx ou site)"), "Lien": (O, "adresse https://", "Lien du document"),
        "Description": (F, TEXTE, "Tiers, catégorie…")}),
    "Libelles": ("Même fichier qu'Ecritures.xlsx, nommé Libelles….xlsx : seuls les libellés sont repris. Chaque Mvt est retrouvé sur le site par sa date, son journal, ses comptes et ses montants (le n° peut différer : fichier venu d'une autre base) ; introuvables, ambigus et exercices clos sont signalés et laissés tels quels.", {}),
    "Banque1": ("Relevé du journal B1. Lignes déjà importées ignorées (date, référence, montant, rang).", {}),
    "Banque2": ("Relevé du journal B2. Lignes déjà importées ignorées (date, référence, montant, rang).", {}),
    "Bit": ("Relevé Bit (journal du réglage releve_bit, B3 à la Loge). Remplace tout le relevé précédent de ce journal (pointages annulés).", {
        "Journ": (O, "code", "Journal du réglage releve_bit (B3 à la Loge) ; toute autre valeur est refusée"), "Date": (O, DATE, ""),
        "Libelle": (O, "texte, 50 car. au plus", "TIERS - RUBRIQUE - SOUS-RUBRIQUE"),
        "Debit": (F, MONTANT, "Entrée d'argent sur Bit (Debit OU Credit)"), "Credit": (F, MONTANT, "Sortie d'argent (Debit OU Credit)")}),
    "Caisse": ("Mouvements de caisse (journal CA). Lignes déjà importées ignorées.", {}),
}
COLONNES_RELEVE = {"Date": (O, DATE, "Date d'opération"), "Référence": (F, TEXTE, "Référence de la banque (אסמכתה)"),
                   "Opération": (F, TEXTE, "Libellé de l'opération (hébreu accepté)"),
                   "Montant": (O, MONTANT, "Positif = entrée, négatif = sortie"),
                   "Solde": (F, MONTANT, "Solde après l'opération ; obligatoire sur la 1re ligne du tout premier import")}
AIDE["Libelles"][1].update({c: v for c, v in AIDE["Ecritures"][1].items()})
for _nom in ("Banque1", "Banque2", "Caisse"):
    AIDE[_nom][1].update(COLONNES_RELEVE)


def classeur_lexique():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    export.feuille(wb, "Fichiers", ["Ordre", "Fichier", "Contenu", "À l'import", "Colonnes (ligne 1)"],
                   [[i, f"{f.nom}.xlsx", f.contenu, AIDE[f.nom][0], " | ".join(f.colonnes)] for i, f in enumerate(FORMATS, 1)])
    export.feuille(wb, "Colonnes", ["Fichier", "Colonne", "Obligatoire", "Format", "Description"],
                   [[f"{f.nom}.xlsx", c, *AIDE[f.nom][1].get(c, ("", "", ""))] for f in FORMATS for c in f.colonnes])
    export.feuille(wb, "Règles", ["Règle", "Détail"], REGLES)
    for ws in wb.worksheets:
        for col, largeur in zip("ABCDE", (22, 24, 40, 60, 60)):
            ws.column_dimensions[col].width = largeur
    return wb


def kit_modeles():
    """ZIP des fichiers types : un modèle vierge par format (ligne 1 = colonnes), le lexique et un mode d'emploi."""
    import io
    import zipfile
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as z:
        for i, f in enumerate(FORMATS, 1):
            octets = io.BytesIO()
            classeur(f, []).save(octets)
            z.writestr(f"{i:02d}_{f.nom}.xlsx", octets.getvalue())
        octets = io.BytesIO()
        classeur_lexique().save(octets)
        z.writestr("Lexique.xlsx", octets.getvalue())
        z.writestr("LISEZMOI.txt", "Modèles vierges des fichiers d'import et d'export de ComptaBB\r\n\r\n"
                   "- Un fichier par nature de données, numéroté dans l'ordre d'import conseillé : chaque fichier ne cite que\r\n"
                   "  des codes définis par les précédents (exercices, réglages, axes, plan comptable, journaux, tiers...).\r\n"
                   "- Ligne 1 = les colonnes attendues, à ne pas modifier ; données à partir de la ligne 2.\r\n"
                   "- Lexique.xlsx : contenu de chaque fichier, colonnes obligatoires, formats et règles.\r\n"
                   "- Pour importer : retirer le numéro du nom (ex. Tiers.xlsx ou Tiers_2026.xlsx), puis\r\n"
                   "  Administration > Imports / Exports > Déposer, puis Importer.\r\n")
    return tampon.getvalue()


def ecrire_lexiques():
    """(Ré)écrit Lexique.xlsx dans Imports et dans Exports ; ignoré si le fichier est ouvert dans Excel."""
    for d in (imports(), exports()):
        try:
            classeur_lexique().save(d / f"{LEXIQUE}.xlsx")
        except OSError:
            pass


def _norme(texte):
    """En-tête comparable : sans accent, majuscule, espace, tiret ni souligné (« Compte de trésorerie » = compte_de_tresorerie)."""
    return "".join(c for c in _sans_accent(str(texte or "")) if c.isalnum())


def entetes_du_fichier(chemin):
    """Première ligne d'un .xlsx (première feuille) ou d'un .csv (point-virgule, virgule ou tabulation) ; [] si illisible."""
    try:
        if Path(chemin).suffix.lower() == ".csv":
            import csv as csv_
            brut = Path(chemin).read_bytes()
            try:
                texte = brut.decode("utf-8-sig")
            except UnicodeDecodeError:
                texte = brut.decode("cp1252", errors="replace")
            premiere = texte.splitlines()[0] if texte.strip() else ""
            sep = max(";,\t", key=premiere.count)
            ligne = next(csv_.reader([premiere], delimiter=sep), [])
        else:
            wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
            try:
                ligne = next(wb.worksheets[0].iter_rows(values_only=True), [])
            finally:
                wb.close()
    except Exception:                                      # fichier abîmé, mot de passe, mauvais format…
        return []
    entetes = [("" if c is None else str(c).strip()) for c in ligne]
    while entetes and not entetes[-1]:
        entetes.pop()
    return entetes


def formats_de_structure(entetes):
    """Formats dont les en-têtes (ligne 1) sont exactement ceux du fichier : même colonnes, même ordre, sans tenir compte
    des accents, des majuscules ni des espaces ; les dernières colonnes facultatives peuvent manquer."""
    vus = [_norme(e) for e in entetes]
    if not vus:
        return []
    trouves = []
    for f in FORMATS:
        base = [_norme(c) for c in f.colonnes]
        permis = [base[:len(base) - k] for k in range(len(f.facultatives) + 1)] + [[_norme(c) for c in x] for x in f.synonymes]
        if vus in permis:                                   # (colonnes libres : AxesComptes se reconnaît par son nom)
            trouves.append(f)
    return trouves


def format_de(chemin):
    """Format d'un fichier : d'après sa **structure** (colonnes de la ligne 1) ; si plusieurs formats ont la même structure
    (relevés de plusieurs journaux, écritures et libellés), le nom du fichier départage ; à défaut de structure
    reconnue, le nom seul (comportement des fichiers plus anciens)."""
    if Path(chemin).suffix.lower() in (".xlsx", ".csv"):
        par_structure = formats_de_structure(entetes_du_fichier(chemin))
        if len(par_structure) == 1:
            return par_structure[0]
        if par_structure:
            return next((f for f in par_structure if f.reconnait(chemin)), None)
    return next((f for f in FORMATS if f.reconnait(chemin)), None)


# ---------------------------------------------------------------- fichiers

def classeur(f, lignes):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = export.feuille(wb, f.nom, f.entetes(), lignes, f.montants)
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, (dt.date, dt.datetime)):
                c.number_format = "DD/MM/YYYY"
    return wb


def exporter(f, auteur=""):
    """Écrit Exports/<Nom>_<AAAA-MM-JJ>.xlsx ; renvoie (chemin, nombre de lignes)."""
    lignes = f.exporter()
    chemin = exports() / f"{f.nom}_{dt.date.today():%Y-%m-%d}.xlsx"
    classeur(f, lignes).save(chemin)
    Modification.objects.create(auteur=auteur, lot="Échanges", action="Export", objet=chemin.name, apres=f"{len(lignes)} ligne(s)")
    return chemin, len(lignes)


def lire(chemin, f):
    """Lignes du fichier : [(n° de ligne Excel, {colonne: valeur})] ; refuse des en-têtes non conformes."""
    if Path(chemin).suffix.lower() == ".csv":             # CSV : point-virgule
        import csv as csv_
        brut = Path(chemin).read_bytes()
        try:
            texte = brut.decode("utf-8-sig")
        except UnicodeDecodeError:                        # fichier enregistré par Excel en Windows-1252
            texte = brut.decode("cp1252", errors="replace")
        wb = None
        sep = max(";,\t", key=(texte.splitlines() or [""])[0].count)
        rangees = iter(list(csv_.reader(io.StringIO(texte), delimiter=sep)))
    else:
        wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
        rangees = wb.worksheets[0].iter_rows(values_only=True)
    entetes = [("" if c is None else str(c).strip()) for c in next(rangees, [])]
    while entetes and not entetes[-1]:
        entetes.pop()
    vus = [_norme(e) for e in entetes]
    permis = [[_norme(c) for c in f.colonnes[:len(f.colonnes) - k]] for k in range(len(f.facultatives) + 1)]
    if f.libres and vus[:len(f.colonnes)] == [_norme(c) for c in f.colonnes] and "" not in entetes:
        colonnes = f.colonnes + entetes[len(f.colonnes):]  # colonnes libres : leurs en-têtes sont les noms des axes
    elif vus in permis or vus in [[_norme(c) for c in x] for x in f.synonymes]:
        colonnes = f.colonnes
    else:
        if wb:
            wb.close()
        raise Refus([f"En-têtes de la ligne 1 non conformes. Attendu : {' | '.join(f.colonnes)}"
                     + (" puis une colonne par axe" if f.libres else "") + f". Trouvé : {' | '.join(entetes) or '(vide)'}."])
    lignes = []
    for n, r in enumerate(rangees, 2):
        r = list(r) + [None] * len(colonnes)
        if any(v not in (None, "") for v in r[:len(colonnes)]):
            lignes.append((n, dict(zip(colonnes, r))))
    if wb:
        wb.close()
    return lignes


def a_importer():
    """Fichiers présents dans Imports : [(chemin, format ou None)] ; les PDF sont des relevés à convertir."""
    return [(p, format_de(p)) for p in sorted(imports().iterdir())
            if p.is_file() and p.suffix.lower() in (".xlsx", ".pdf", ".csv") and not p.name.startswith("~$") and p.stem != LEXIQUE]


def retirer(nom, auteur=""):
    """Supprime un fichier du dossier Imports (déposé par erreur, ou devenu inutile). Le dossier Importés n'est pas touché."""
    chemin = next((p for p, _ in a_importer() if p.name == nom), None)
    if not chemin:
        raise Refus([f"« {nom} » n'est pas (ou plus) dans le dossier Imports."])
    chemin.unlink()
    Modification.objects.create(auteur=auteur, lot="Échanges", action="Fichier retiré du dossier Imports", objet=nom[:200])


DEPOSABLES = (".xlsx", ".pdf", ".csv")


def deposer(nom, contenu, auteur=""):
    """Dépose dans Imports un fichier envoyé par le navigateur (.xlsx, .pdf, ou .zip dont les .xlsx et .pdf sont extraits).

    Renvoie les noms déposés ; un fichier de même nom est remplacé."""
    import io
    import zipfile
    nom = Path(nom.replace("\\", "/")).name
    if Path(nom).suffix.lower() == ".zip":
        try:
            z = zipfile.ZipFile(io.BytesIO(contenu))
        except zipfile.BadZipFile:
            raise Refus([f"{nom} : ZIP illisible."]) from None
        with z:
            fichiers = [(n.replace("\\", "/").rsplit("/", 1)[-1], n) for n in z.namelist() if not n.endswith("/")
                        and not n.startswith("__MACOSX")]
            fichiers = [(b, n) for b, n in fichiers if Path(b).suffix.lower() in DEPOSABLES and not b.startswith("~$")]
            if not fichiers:
                raise Refus([f"{nom} : aucun fichier .xlsx ou .pdf dans le ZIP."])
            return [n for b, n_ in fichiers for n in deposer(b, z.read(n_), auteur)]
    if Path(nom).suffix.lower() not in DEPOSABLES or not nom or nom.startswith("."):
        raise Refus([f"{nom} : fichier .xlsx, .pdf ou .zip attendu."])
    (imports() / nom).write_bytes(contenu)
    Modification.objects.create(auteur=auteur, lot="Échanges", action="Dépôt dans Imports", objet=nom[:200])
    return [nom]


def importer_tout(utilisateur=None):
    """Importe tous les fichiers reconnus du dossier Imports dans l'ordre du lexique, tout ou rien : à la moindre erreur,
    rien n'est enregistré. Rien n'est supprimé (contrairement à Tout réinjecter). Renvoie (comptes rendus, ignorés)."""
    from .base_donnees import sauvegarder
    ordre = {f.nom: i for i, f in enumerate(FORMATS)}
    choisis = sorted(((f, p) for p, f in a_importer() if f and p.suffix.lower() in (".xlsx", ".csv")),
                     key=lambda x: (ordre[x[0].nom], x[1].name.lower()))
    ignores = [p.name for p, f in a_importer() if not f and p.suffix.lower() == ".xlsx"]
    if not choisis:
        raise Refus(["Aucun fichier à importer dans le dossier Imports."])
    lus, erreurs = [], []
    for f, chemin in choisis:
        try:
            lus.append((f, chemin, lire(chemin, f)))
        except Refus as e:
            erreurs += [f"{chemin.name} : {x}" for x in e.erreurs]
    if erreurs:
        raise Refus(erreurs)
    sauvegarder("avant-import")
    auteur = utilisateur.get_username() if utilisateur else ""
    comptes_rendus = []
    with transaction.atomic():
        for f, chemin, lignes in lus:
            try:
                texte = f.importer(lignes, chemin.name, utilisateur) if lignes else "vide"
            except Refus as e:
                raise Refus([f"{chemin.name} : {x}" for x in e.erreurs] + [
                    f"Rien n'a été enregistré. Corriger {chemin.name}, le déposer à nouveau, puis relancer Tout importer."])
            Modification.objects.create(auteur=auteur, lot="Échanges", action=f"Import {f.nom}", objet=chemin.name[:200],
                                        apres=texte[:300])
            comptes_rendus.append(f"{chemin.name} : {texte}")
    for _, chemin, _ in lus:
        ranger(chemin)
    return comptes_rendus, ignores


def fichiers_exportes():
    """Fichiers du dossier Exports (à télécharger depuis le navigateur), du plus récent au plus ancien."""
    return sorted((p for p in exports().iterdir() if p.is_file() and p.suffix.lower() in (".xlsx", ".zip")
                   and not p.name.startswith("~$")), key=lambda p: p.stat().st_mtime, reverse=True)


def ranger(chemin):
    """Déplace un fichier traité dans Imports/Importés, avec la date et l'heure."""
    dest = importes() / f"{chemin.stem}_importé_{dt.datetime.now():%Y-%m-%d_%H%M%S}{chemin.suffix}"
    shutil.move(str(chemin), dest)
    return dest


def fichier_d_import(nom):
    """Chemin d'un fichier du dossier Imports désigné par son nom (jamais en dehors du dossier)."""
    chemin = imports() / Path(nom).name
    if not chemin.is_file():
        raise Refus([f"Fichier {nom} absent du dossier Imports."])
    return chemin


def importer(nom, utilisateur=None):
    """Importe un fichier du dossier Imports (tout ou rien), puis le range dans Importés. Renvoie (format, résumé)."""
    from .base_donnees import sauvegarder
    chemin = fichier_d_import(nom)
    f = format_de(chemin)
    if not f or chemin.suffix.lower() not in (".xlsx", ".csv"):
        raise Refus([f"{chemin.name} : structure non reconnue. La ligne 1 doit contenir exactement les colonnes de l'un des "
                     "fichiers décrits dans le lexique (Tiers, Journaux, Ecritures…), dans le même ordre."])
    lignes = lire(chemin, f)
    if not lignes:
        raise Refus([f"{chemin.name} : aucune ligne de données."])
    sauvegarder("avant-import")
    auteur = utilisateur.get_username() if utilisateur else ""
    with transaction.atomic():
        texte = f.importer(lignes, chemin.name, utilisateur)
        Modification.objects.create(auteur=auteur, lot="Échanges", action=f"Import {f.nom}", objet=chemin.name[:200],
                                    apres=texte[:300])
    ranger(chemin)
    return f, texte


def convertir_pdf(nom, code, auteur=""):
    """Relevé PDF (Mizrahi ou tableau) du dossier Imports → Imports/Banque1_<date>.xlsx (ou Banque2), à vérifier puis importer."""
    chemin = fichier_d_import(nom)
    if chemin.suffix.lower() != ".pdf":
        raise Refus([f"{chemin.name} n'est pas un PDF."])
    lignes = releves.lire(chemin.name, chemin.read_bytes())
    if not lignes:
        raise Refus([f"{chemin.name} : aucune opération reconnue dans le PDF."])
    f = PAR_NOM["Banque1" if code == "B1" else "Banque2"]
    dest = imports() / f"{f.nom}_{dt.date.today():%Y-%m-%d}.xlsx"
    classeur(f, [[l["date"], l["reference"], l["operation"], l["montant"], l["solde"]] for l in lignes]).save(dest)
    ranger(chemin)
    Modification.objects.create(auteur=auteur, lot="Échanges", action="Conversion PDF", objet=chemin.name[:200],
                                apres=f"{dest.name} : {len(lignes)} ligne(s)")
    return dest, len(lignes)


# ---------------------------------------------------------------- tout réinjecter

RELEVES = {"Banque1": "B1", "Banque2": "B2", "Caisse": "CA"}      # Bit : son import remplace déjà le relevé B3


def fichiers_a_reinjecter():
    """Un fichier par format présent dans Imports, dans l'ordre d'import ; refus si un format a plusieurs fichiers."""
    par_format = defaultdict(list)
    for p, f in a_importer():
        if f and p.suffix.lower() == ".xlsx":
            par_format[f.nom].append(p)
    doubles = [f"{nom} : {len(ps)} fichiers ({', '.join(p.name for p in ps)}) ; n'en laisser qu'un." for nom, ps in par_format.items()
               if len(ps) > 1]
    if doubles:
        raise Refus(doubles)
    return [(f, par_format[f.nom][0]) for f in FORMATS if f.nom in par_format]


def _cle_releve(l):
    return (l.journal_id, l.date, l.reference, l.montant, l.rang, l.ouverture)


def _memoriser():
    """Ce qui renvoie aux écritures et aux relevés, repéré par des clés qui survivent à la réinjection."""
    return {
        "mvts": {m.numero: (m.origine, m.commentaire, m.cree_par_id) for m in Mouvement.objects.all()},
        "an": {e.pk: e.mouvement_an.numero for e in Exercice.objects.filter(mouvement_an__isnull=False).select_related("mouvement_an")},
        "fiches": {l.pk: l.mouvement.numero for l in LigneFiche.objects.filter(mouvement__isnull=False).select_related("mouvement")},
        "pointages": [(r.journal_id, r.mode, r.cree_par_id, [_cle_releve(l) for l in r.releves.all()],
                       [(l.mouvement.numero, l.ordre) for l in r.ecritures.select_related("mouvement")])
                      for r in Rapprochement.objects.prefetch_related("releves", "ecritures")],
    }


def _retablir(memo):
    """Recolle les liens dont les deux côtés existent encore ; renvoie le nombre de liens perdus."""
    perdus = 0
    for numero, (origine, commentaire, cree_par) in memo["mvts"].items():
        Mouvement.objects.filter(numero=numero).update(origine=origine, commentaire=commentaire, cree_par_id=cree_par)
    mvts = dict(Mouvement.objects.values_list("numero", "pk"))
    for pk, numero in memo["an"].items():
        if numero in mvts:
            Exercice.objects.filter(pk=pk).update(mouvement_an_id=mvts[numero])
        else:
            perdus += 1
    for pk, numero in memo["fiches"].items():
        if numero in mvts:
            LigneFiche.objects.filter(pk=pk).update(mouvement_id=mvts[numero])
        else:
            perdus += 1
    releves = {_cle_releve(l): l.pk for l in LigneReleve.objects.filter(rapprochement__isnull=True)}
    ecritures = {(n, o): pk for pk, n, o in Ligne.objects.filter(rapprochement__isnull=True)
                 .values_list("pk", "mouvement__numero", "ordre")}
    for journal, mode, cree_par, cles_r, cles_e in memo["pointages"]:
        rs, es = [releves.get(k) for k in cles_r], [ecritures.get(k) for k in cles_e]
        if None in rs or None in es:
            perdus += 1
            continue
        r = Rapprochement.objects.create(journal_id=journal, mode=mode, cree_par_id=cree_par)
        LigneReleve.objects.filter(pk__in=rs).update(rapprochement=r)
        Ligne.objects.filter(pk__in=es).update(rapprochement=r)
    return perdus


def reinjecter(utilisateur=None):
    """Remplace les données par les fichiers du dossier Imports, tout ou rien.

    Un fichier d'écritures, de relevé (Banque1, Banque2, Bit, Caisse) ou de budget remplace entièrement les données de sa
    nature ; les référentiels sont mis à jour (jamais supprimés : les écritures y renvoient). Pointages, à-nouveaux et
    fiches bénévoles reportées sont recollés quand leurs écritures et lignes de relevé reviennent à l'identique."""
    from .base_donnees import sauvegarder
    choisis = fichiers_a_reinjecter()
    if not choisis:
        raise Refus(["Aucun fichier à réinjecter dans le dossier Imports."])
    lus, erreurs = [], []
    for f, chemin in choisis:
        try:
            lus.append((f, chemin, lire(chemin, f)))
        except Refus as e:
            erreurs += [f"{chemin.name} : {x}" for x in e.erreurs]
    if erreurs:
        raise Refus(erreurs)
    sauvegarde = sauvegarder("avant-reinjection")
    noms = {f.nom for f, _, _ in lus}
    comptes_rendus = []
    with transaction.atomic():
        memo = _memoriser()
        Rapprochement.objects.all().delete()
        if "Ecritures" in noms:
            Exercice.objects.update(mouvement_an=None)
            LigneFiche.objects.update(mouvement=None)
            Mouvement.objects.all().delete()
        for nom, code in RELEVES.items():
            if nom in noms:
                LigneReleve.objects.filter(journal_id=code).delete()
        if "Budget" in noms:
            Budget.objects.all().delete()
        for f, chemin, lignes in lus:
            try:
                texte = f.importer(lignes, chemin.name, utilisateur) if lignes else "vide"
            except Refus as e:
                raise Refus([f"{chemin.name} : {x}" for x in e.erreurs])
            comptes_rendus.append(f"{chemin.name} : {texte}")
        perdus = _retablir(memo)
        if perdus:
            comptes_rendus.append(f"{perdus} lien(s) non recollé(s) (pointage, à-nouveau ou fiche dont l'écriture a changé)")
        Modification.objects.create(auteur=utilisateur.get_username() if utilisateur else "", lot="Échanges",
                                    action="Réinjection", objet=", ".join(f.nom for f, _, _ in lus)[:200],
                                    avant=sauvegarde.name[:300], apres=" ; ".join(comptes_rendus)[:300])
    for _, chemin, _ in lus:
        ranger(chemin)
    return comptes_rendus, sauvegarde

