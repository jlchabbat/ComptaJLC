"""Adaptation d'un extrait SUMIT retravaillé (classeur « EXTRACT_SUMIT_… ») en fichiers d'import de l'application web.

Le classeur source est lu en valeurs (celles calculées par Excel au dernier enregistrement), jamais enregistré.
Feuilles lues : Plan (comptes, journaux, codes axe 1 et axe 2), Tiers (comptes de tiers et coordonnées), Ecritures
(2 ou 4 lignes par opération de la Base), Base (lien « Pièce PDF » du document SUMIT de chaque opération).

Fichiers produits (dossier de sortie, et leur ZIP adaptation_sumit.zip à côté), importés dans cet ordre :
    Exercices.xlsx, Axe1.xlsx, Axe2.xlsx, Prefixes.xlsx, PlanComptable.xlsx, Journaux.xlsx, Tiers.xlsx, Ecritures.xlsx
    (Administration › Imports / Exports), puis
    Liens_documents.xlsx (format Liens) : un lien SUMIT par opération, avec son n° de Mvt.
    Dans l'appli : déposer le ZIP de ces fichiers dans Administration › Imports / Exports, puis « Tout importer ».
    Rapport.txt : chiffres, points à vérifier, types de tiers à créer avant l'import.

Mvt = premier Mvt (1 par défaut) - 1 + N° base ; Pièce = N° base. Une ligne de bilan (classes 1 à 5) prend le code
axe 2 de la ligne 6/7 de son opération, à défaut le code général (--axe2-defaut, GEN1).

Chaque nouveau tiers prend un compte au préfixe de son type (Membre 411, Fournisseur 401, Amis du Bnei Brith 412 ;
--type TYPE=PREFIXE pour un autre) : 411LINDA001 d'un ami devient 412LINDA001, dans Tiers.xlsx et dans les écritures.

Tiers : le fichier Tiers existant est respecté. Ses tiers (export Tiers.xlsx du site passé par --tiers-existant, à
défaut les tiers d'origine « Fichier Tiers » du classeur) ne sont pas repris dans Tiers.xlsx : leurs fiches et
coordonnées sur le site restent telles quelles. Seuls les nouveaux tiers sont ajoutés.

    python src/adaptation_sumit.py EXTRACT_SUMIT.xlsx [--tiers-existant Tiers_export.xlsx] [--sortie dossier]
                                   [--premier-mvt 1] [--axe2-defaut GEN1]
"""

import argparse
import datetime as dt
import re
import sys
from collections import Counter, defaultdict, OrderedDict
from decimal import Decimal
from pathlib import Path

import openpyxl

RACINE = Path(__file__).resolve().parent.parent
TIERS = ["Compte", "Type", "Nom", "Prénom", "Adresse", "Code postal", "Ville", "Téléphone", "E-mail",
         "Date d'adhésion", "Statut", "Cotisation annuelle"]
ECRITURES = ["Date", "Jnl", "Mvt", "Pièce", "Compte", "Libellé", "Débit", "Crédit", "Anal2", "Let"]
PREFIXES_TYPES = {"Membre": "411", "Fournisseur": "401", "Amis du Bnei Brith": "412"}   # types de tiers du site (--type)


def _texte(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def _montant(v):
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


def _jour(v):
    return v.date() if isinstance(v, dt.datetime) else v


def _tableau(ws, entete, colonnes, debut=1):
    """Lignes (dict) du tableau de ws dont la ligne d'en-tête contient `entete` en première colonne demandée."""
    rangees = list(ws.iter_rows(min_row=debut, values_only=True))
    for i, r in enumerate(rangees):
        noms = [_texte(v) for v in r]
        if entete in noms:
            idx = {}
            for c in colonnes:                            # une même étiquette peut revenir plus loin (autre tableau)
                idx[c] = noms.index(c, noms.index(entete))
            res = []
            for r2 in rangees[i + 1:]:
                d = {c: (r2[k] if k < len(r2) else None) for c, k in idx.items()}
                if d[entete] in (None, ""):
                    continue
                res.append(d)
            return res
    raise ValueError(f"Feuille {ws.title} : en-tête « {entete} » introuvable.")


def lire(chemin):
    wb = openpyxl.load_workbook(chemin, data_only=True)
    for f in ("Plan", "Tiers", "Ecritures", "Base"):
        if f not in wb.sheetnames:
            raise ValueError(f"Feuille « {f} » absente : ce n'est pas un extrait SUMIT retravaillé.")
    plan = wb["Plan"]
    s = {
        "comptes": _tableau(plan, "Compte", ["Compte", "Libellé", "Axe1"]),
        "journaux": _tableau(plan, "Journal", ["Journal", "Intitulé", "Compte"]),
        "axe1": _tableau(plan, "Code Axe1", ["Code Axe1", "Libellé Axe1"]),
        "axe2": _tableau(plan, "Code Axe2", ["Code Axe2", "Libellé Axe2"]),
        "tiers": _tableau(wb["Tiers"], "Compte", TIERS[:9] + ["Date d'adhésion", "Cotisation annuelle", "Statut", "Origine"]),
        "remarques": _tableau(wb["Tiers"], "Tiers SUMIT", ["Tiers SUMIT", "Compte tiers", "Remarque"]),
        "ecritures": _tableau(wb["Ecritures"], "Journ", ["Journ", "Date", "Compte", "Libellé écriture", "Débit", "Crédit",
                                                       "AnalAxe2", "N° base", "Ligne"]),
        "base": _tableau(wb["Base"], "N°", ["N°", "Date", "Tiers", "Montant", "Catégorie", "Type paiement", "Pièce PDF"]),
        "intitules": {},
    }
    s["axe1"] = [a for a in s["axe1"] if re.fullmatch(r"[A-Z]+\d+", _texte(a["Code Axe1"]))]   # lignes de contrôle exclues
    for ws in wb.worksheets:                              # « Journal B1 - BANQUE MIZRAHI COMPTE COURANT » en A1
        m = re.match(r"Journal (\w+) - (.+)", _texte(ws["A1"].value))
        if m:
            s["intitules"][m.group(1)] = m.group(2).strip()
    for b in s["base"]:                                   # lien = hyperlien de la cellule, ou adresse écrite
        b["Pièce PDF"] = _texte(b["Pièce PDF"])
    ws = wb["Base"]
    entetes = [_texte(c.value) for c in ws[1]]
    k = entetes.index("Pièce PDF")
    liens = {}
    for r in ws.iter_rows(min_row=2):
        if r[k].hyperlink and r[k].hyperlink.target:
            liens[r[0].value] = r[k].hyperlink.target
    for b in s["base"]:
        b["lien"] = liens.get(b["N°"]) or (b["Pièce PDF"] if b["Pièce PDF"].startswith("https://") else "")
    return s


def lire_tiers_existants(chemin):
    """Comptes du fichier Tiers existant (export Tiers.xlsx du site) : {compte: (nom, prénom)}."""
    wb = openpyxl.load_workbook(chemin, read_only=True, data_only=True)
    rangees = wb.worksheets[0].iter_rows(values_only=True)
    entetes = [_texte(v) for v in next(rangees, [])]
    if "Compte" not in entetes or "Nom" not in entetes:
        raise ValueError(f"{chemin} : colonnes Compte et Nom attendues (export Tiers.xlsx du site).")
    k, n = entetes.index("Compte"), entetes.index("Nom")
    p = entetes.index("Prénom") if "Prénom" in entetes else None
    res = {}
    for r in rangees:
        if r[k] not in (None, ""):
            res[_texte(r[k])] = (_texte(r[n]), _texte(r[p]) if p is not None else "")
    wb.close()
    return res


def _personne(nom, prenom):
    return re.sub(r"[^A-Z]", "", f"{nom}{prenom}".upper())


def adapter(s, premier_mvt=1, axe2_defaut="GEN1", existants=None, prefixes_types=None):
    """Renvoie ({nom de fichier: (en-têtes, lignes)}, rapport). existants : fichier Tiers existant ({compte: (nom,
    prénom)}) ; à défaut, les tiers d'origine « Fichier Tiers » du classeur. Les tiers existants ne sont jamais
    repris dans Tiers.xlsx : leurs fiches et coordonnées restent celles du site ; seuls les nouveaux tiers sont ajoutés."""
    rapport, alertes = [], []
    fichiers = OrderedDict()
    decalage = premier_mvt - 1

    # écritures, groupées par opération (N° base)
    ops = defaultdict(list)
    for e in s["ecritures"]:
        ops[int(e["N° base"])].append(e)
    dates = sorted(_jour(e["Date"]) for e in s["ecritures"])
    annees = sorted({d.year for d in dates})
    fichiers["Exercices.xlsx"] = (["Libellé", "Début", "Fin", "Clos"],
                                  [[str(a), dt.date(a, 1, 1), dt.date(a, 12, 31), "non"] for a in annees])
    fichiers["Axe1.xlsx"] = (["Code", "Libellé"], [[_texte(a["Code Axe1"]), _texte(a["Libellé Axe1"])] for a in s["axe1"]])
    codes2 = [[_texte(a["Code Axe2"]), _texte(a["Libellé Axe2"]), 1] for a in s["axe2"]]
    if axe2_defaut not in {c[0] for c in codes2}:
        codes2.insert(0, [axe2_defaut, "Général", 1])
    fichiers["Axe2.xlsx"] = (["Code", "Libellé", "Statut"], codes2)
    prefixes = OrderedDict()
    for axe, codes in ((1, fichiers["Axe1.xlsx"][1]), (2, codes2)):
        for c in codes:
            p = re.match(r"[A-Z]+", c[0]).group()
            prefixes.setdefault(p, [p, axe, (c[1] if axe == 1 else "")[:60]])
    fichiers["Prefixes.xlsx"] = (["Préfixe", "Axe", "Libellé"], list(prefixes.values()))

    # plan comptable (les comptes de tiers auxiliaires viennent de Tiers.xlsx)
    plan = [[_texte(c["Compte"]), _texte(c["Libellé"]), _texte(c["Axe1"]),
             "oui" if _texte(c["Compte"]).startswith(("401", "411")) else "non", "oui"] for c in s["comptes"]]
    journaux = []
    for j in s["journaux"]:
        code = _texte(j["Journal"])
        journaux.append([code, s["intitules"].get(code, _texte(j["Intitulé"]))[:60],
                         "BQ" if _texte(j["Compte"]).startswith("512") else ("CA" if _texte(j["Compte"]).startswith("53") else code),
                         _texte(j["Compte"]), "oui"])
    fichiers["Journaux.xlsx"] = (["Code", "Intitulé", "Type", "Compte de trésorerie", "Actif"], journaux)

    # tiers : nouveaux comptes auxiliaires seulement (un compte tout en chiffres est un collectif du plan) ;
    # le fichier Tiers existant est respecté : ses tiers ne sont ni modifiés ni recréés
    source = "fichier Tiers existant" if existants is not None else "origine « Fichier Tiers » du classeur"
    if existants is None:
        existants = {_texte(t["Compte"]): (_texte(t["Nom"]), _texte(t["Prénom"])) for t in s["tiers"]
                     if _texte(t["Origine"]) == "Fichier Tiers"}
    personnes = {_personne(*v): c for c, v in existants.items()}
    prefixes_types = prefixes_types or PREFIXES_TYPES
    tiers, types, gardes, renumerotes = [], Counter(), 0, {}
    pris = {_texte(t["Compte"]) for t in s["tiers"]} | set(existants) | {c[0] for c in plan}
    for t in s["tiers"]:
        compte = _texte(t["Compte"])
        if compte.isdigit():
            continue
        if compte in existants:
            gardes += 1
            if _personne(*existants[compte]) != _personne(t["Nom"], t["Prénom"]):
                alertes.append(f"Tiers {compte} : « {_texte(t['Nom'])} {_texte(t['Prénom'])} » dans le classeur, "
                               f"« {' '.join(existants[compte])} » dans le fichier Tiers existant (gardé tel quel).")
            continue
        homonyme = personnes.get(_personne(t["Nom"], t["Prénom"]))
        if homonyme:
            alertes.append(f"Nouveau tiers {compte} ({_texte(t['Nom'])} {_texte(t['Prénom'])}) : même nom que {homonyme} "
                           "du fichier Tiers existant — vérifier s'il s'agit de la même personne.")
        prefixe = prefixes_types.get(_texte(t["Type"]))
        if prefixe and not compte.startswith(prefixe):      # compte du préfixe du type : 411LINDA001 → 412LINDA001
            nouveau, rang = prefixe + compte[3:], 1
            while nouveau in pris:
                m = re.match(r"(.*?)(\d+)$", nouveau)
                rang = int(m.group(2)) + 1 if m else rang + 1
                nouveau = f"{m.group(1)}{rang:0{len(m.group(2))}d}" if m else f"{prefixe}{compte[3:]}{rang:03d}"
            pris.add(nouveau)
            renumerotes[compte] = nouveau
            compte = nouveau
        types[_texte(t["Type"])] += 1
        tiers.append([compte, _texte(t["Type"]), _texte(t["Nom"]), _texte(t["Prénom"]), _texte(t["Adresse"]),
                      _texte(t["Code postal"]), _texte(t["Ville"]), _texte(t["Téléphone"]), _texte(t["E-mail"]),
                      _jour(t["Date d'adhésion"]) or None, _texte(t["Statut"]),
                      t["Cotisation annuelle"] if t["Cotisation annuelle"] not in (None, "") else None])
    fichiers["Tiers.xlsx"] = (TIERS, tiers)

    touches = [c for c in plan if c[0] in existants]           # comptes du fichier Tiers existant : laissés tels quels
    plan = [c for c in plan if c[0] not in existants]
    if touches:
        rapport_plan = "Comptes du fichier Tiers existant retirés du plan (inchangés sur le site) : " + ", ".join(c[0] for c in touches) + "."
        alertes.insert(0, rapport_plan)
    fichiers["PlanComptable.xlsx"] = (["Compte", "Libellé", "Axe 1", "Lettrable", "Actif"], plan)
    fichiers.move_to_end("Journaux.xlsx")
    connus = {c[0] for c in plan} | {t[0] for t in tiers} | set(existants)
    lignes = []
    for n, ls in sorted(ops.items()):
        ls.sort(key=lambda e: e["Ligne"] or 0)
        axe2 = next((_texte(e["AnalAxe2"]) for e in ls if _texte(e["AnalAxe2"])), axe2_defaut)
        td = sum(_montant(e["Débit"]) for e in ls)
        tc = sum(_montant(e["Crédit"]) for e in ls)
        if td != tc:
            alertes.append(f"N° base {n} déséquilibré : débit {td} ≠ crédit {tc}.")
        for e in ls:
            compte = _texte(e["Compte"])
            compte = renumerotes.get(compte, compte)
            if compte not in connus:
                alertes.append(f"N° base {n} : compte {compte} absent du Plan et des Tiers.")
            d, c = _montant(e["Débit"]), _montant(e["Crédit"])
            if d == c == 0:                               # opération à 0 (annulée dans SUMIT)
                continue
            lignes.append([_jour(e["Date"]), _texte(e["Journ"]), n + decalage, n, compte, _texte(e["Libellé écriture"])[:200],
                           float(d) if d else None, float(c) if c else None, _texte(e["AnalAxe2"]) or axe2, ""])
    ecrits = {l[3] for l in lignes}
    vides = sorted(set(ops) - ecrits)
    if vides:
        alertes.append("Opérations à montant nul, non reprises : N° base " + ", ".join(map(str, vides)) + ".")
    fichiers["Ecritures.xlsx"] = (ECRITURES, lignes)

    # liens des documents SUMIT : un par opération, avec son n° de Mvt
    base = {int(b["N°"]): b for b in s["base"]}
    liens = []
    for n, b in sorted(base.items()):
        if not b["lien"]:
            continue
        if n not in ecrits:
            alertes.append(f"N° base {n} : document SUMIT sans écriture ({b['lien']}).")
            continue
        d = _jour(b["Date"])
        description = " · ".join(x for x in (_texte(b["Tiers"]), _texte(b["Catégorie"]),
                                             f"{d:%d/%m/%Y}" if isinstance(d, dt.date) else "",
                                             f"{abs(float(b['Montant'] or 0)):.2f}") if x)
        liens.append([n + decalage, b["lien"], description[:150]])
    fichiers["Liens_documents.xlsx"] = (["Mvt", "Lien", "Description"], liens)

    hors = Counter(d.year for d in dates if d.year != annees[-1])
    rapport += [
        f"Opérations : {len(ecrits)} (Mvt {min(ecrits) + decalage} à {max(ecrits) + decalage}), lignes d'écriture : {len(lignes)}.",
        f"Comptes du plan : {len(plan)}.",
        f"Tiers existants gardés tels quels ({source}) : {gardes} ; nouveaux tiers dans Tiers.xlsx : {len(tiers)} "
        f"({', '.join(f'{k} {v}' for k, v in types.items())}).",
        f"Codes axe 1 : {len(fichiers['Axe1.xlsx'][1])}, axe 2 : {len(codes2)}, journaux : {len(journaux)}.",
        f"Documents SUMIT rattachés à leur Mvt : {len(liens)}.",
    ]
    if renumerotes:
        rapport.append(f"Comptes renumérotés d'après le préfixe de leur type de tiers : {len(renumerotes)} ("
                       + ", ".join(f"{a} → {b}" for a, b in list(renumerotes.items())[:3]) + "…).")
    nouveaux = sorted(set(types) - set(prefixes_types))
    if nouveaux:
        rapport.append("Types de tiers inconnus (à créer dans Administration › Référentiels › Types de tiers, puis "
                       "relancer avec --type) : " + ", ".join(f"« {t} »" for t in nouveaux) + ".")
    if hors:
        rapport.append("Dates hors de l'exercice " + str(annees[-1]) + " : " + ", ".join(f"{v} ligne(s) en {a}" for a, v in hors.items())
                       + " — refusées si cet exercice est clos sur le site (RG-04).")
    for r in s["remarques"]:
        if _texte(r["Remarque"]):
            c = _texte(r["Compte tiers"])
            alertes.append(f"Remarque du classeur — {_texte(r['Tiers SUMIT'])} ({renumerotes.get(c, c)}) : {_texte(r['Remarque'])}")
    rapport += alertes or ["Aucune anomalie : chaque opération est équilibrée, tous ses comptes existent."]
    return fichiers, rapport


def ecrire(fichiers, rapport, sortie):
    sortie.mkdir(parents=True, exist_ok=True)
    for nom, (entetes, lignes) in fichiers.items():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = nom.rsplit(".", 1)[0]
        ws.append(entetes)
        for r in lignes:
            ws.append(r)
        for cellule in ws[1]:
            cellule.font = openpyxl.styles.Font(bold=True)
        for k, e in enumerate(entetes, 1):
            if e in ("Date", "Début", "Fin", "Date d'adhésion"):
                for (c,) in ws.iter_rows(min_row=2, min_col=k, max_col=k):
                    c.number_format = "dd/mm/yyyy"
            if e == "Lien":
                for (c,) in ws.iter_rows(min_row=2, min_col=k, max_col=k):
                    c.hyperlink = c.value
            ws.column_dimensions[openpyxl.utils.get_column_letter(k)].width = max(10, min(60, len(e) + 6))
        wb.save(sortie / nom)
    (sortie / "Rapport.txt").write_text("\n".join(rapport) + "\n", encoding="utf-8")
    import zipfile
    with zipfile.ZipFile(sortie.with_suffix(".zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for nom in list(fichiers) + ["Rapport.txt"]:
            z.write(sortie / nom, nom)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("classeur")
    p.add_argument("--sortie", default=str(RACINE / "Imports" / "adaptation_sumit"))
    p.add_argument("--premier-mvt", type=int, default=1)
    p.add_argument("--axe2-defaut", default="GEN1")
    p.add_argument("--type", action="append", default=[], metavar="TYPE=PREFIXE",
                   help="type de tiers du site et préfixe de ses comptes (s'ajoute à Membre=411, Fournisseur=401, "
                        "Amis du Bnei Brith=412)")
    p.add_argument("--tiers-existant", help="export Tiers.xlsx du site : ses tiers ne sont ni modifiés ni recréés")
    a = p.parse_args(argv)
    existants = lire_tiers_existants(a.tiers_existant) if a.tiers_existant else None
    types = dict(PREFIXES_TYPES, **dict(t.split("=", 1) for t in a.type))
    fichiers, rapport = adapter(lire(a.classeur), a.premier_mvt, a.axe2_defaut, existants, types)
    ecrire(fichiers, rapport, Path(a.sortie))
    print("\n".join(rapport))
    print(f"Fichiers écrits dans {a.sortie}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
