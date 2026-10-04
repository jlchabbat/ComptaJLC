"""Lecture des fichiers CSV d'import : plan comptable, codes Axe 1, codes Axe 2."""
import csv
import io
import unicodedata
from datetime import date, datetime

from .models import STATUTS


class ErreurImport(Exception):
    def __init__(self, erreurs):
        super().__init__("; ".join(erreurs))
        self.erreurs = erreurs


def norm(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def decoder(octets):
    """UTF-8 (avec ou sans BOM), sinon Windows-1252 (export Excel français)."""
    try:
        return octets.decode("utf-8-sig")
    except UnicodeDecodeError:
        return octets.decode("cp1252", errors="replace")


def lire(octets, colonnes_requises, colonnes_facultatives=()):
    """Retourne [(n° de ligne, {colonne normalisée: valeur})]. Colonnes repérées par leur titre."""
    texte = decoder(octets)
    delim = ";" if texte.count(";") >= texte.count(",") else ","
    lignes = list(csv.reader(io.StringIO(texte), delimiter=delim))
    if not lignes:
        raise ErreurImport(["Fichier vide."])
    titres = [norm(t) for t in lignes[0]]
    manque = [c for c in colonnes_requises if c not in titres]
    if manque:
        raise ErreurImport([f"Colonne « {c} » absente (titres lus : {', '.join(lignes[0])})." for c in manque])
    out = []
    for n, row in enumerate(lignes[1:], start=2):
        if not any(c.strip() for c in row):
            continue
        d = {t: (row[k].strip() if k < len(row) else "") for k, t in enumerate(titres)}
        out.append((n, d))
    return out


def statut(texte):
    if not texte:
        return 1
    t = norm(texte)
    for k, v in STATUTS.items():
        if t in (norm(v), str(k)):
            return k
    raise ValueError(f"statut « {texte} » inconnu (En cours, Terminé ou Non affecté)")


def booleen(texte, defaut):
    if not texte:
        return defaut
    t = norm(texte)
    if t in ("oui", "o", "1", "vrai", "true", "x"):
        return True
    if t in ("non", "n", "0", "faux", "false"):
        return False
    raise ValueError(f"« {texte} » : répondre Oui ou Non")


def lire_codes(octets):
    """Fichier Code;Libellé;Statut -> [(code, libellé, statut)]."""
    out, erreurs, vus = [], [], set()
    for n, d in lire(octets, ["code", "libelle"]):
        try:
            if not d["code"] or not d["libelle"]:
                raise ValueError("code et libellé obligatoires")
            if d["code"] in vus:
                raise ValueError(f"code « {d['code']} » en double")
            vus.add(d["code"])
            out.append((d["code"], d["libelle"], statut(d.get("statut", ""))))
        except ValueError as e:
            erreurs.append(f"Ligne {n} : {e}")
    if erreurs:
        raise ErreurImport(erreurs)
    return out


def lire_plan(octets, codes_axe1):
    """Fichier Compte;Libellé;Axe 1;Lettrable;Actif -> [(compte, libellé, axe1|None, lettrable, actif)]."""
    out, erreurs, vus = [], [], set()
    for n, d in lire(octets, ["compte", "libelle"]):
        try:
            if not d["compte"].isdigit() or not d["libelle"]:
                raise ValueError("numéro de compte (chiffres) et libellé obligatoires")
            if d["compte"] in vus:
                raise ValueError(f"compte « {d['compte']} » en double")
            vus.add(d["compte"])
            axe1 = d.get("axe 1", "") or None
            if axe1 and axe1 not in codes_axe1:
                raise ValueError(f"code Axe 1 « {axe1} » inconnu : importez d'abord les codes Axe 1")
            out.append((d["compte"], d["libelle"], axe1,
                        booleen(d.get("lettrable", ""), False), booleen(d.get("actif", ""), True)))
        except ValueError as e:
            erreurs.append(f"Ligne {n} : {e}")
    if erreurs:
        raise ErreurImport(erreurs)
    return out


def montant(texte):
    """« 1 600.00 », « 1600,50 », « 1.600,50 » -> centimes (entier)."""
    t = (texte or "").replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    if not t:
        return 0
    if "," in t and "." in t:  # le dernier séparateur est la décimale
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        t = t.replace("," if dec == "." else ".", "").replace(dec, ".")
    else:
        t = t.replace(",", ".")
    try:
        euros, _, cts = t.partition(".")
        if not (euros.lstrip("-").isdigit() and (not cts or cts.isdigit())):
            raise ValueError
        v = abs(int(euros)) * 100 + int((cts + "00")[:2]) + (1 if len(cts) > 2 and cts[2] >= "5" else 0)
        return -v if euros.startswith("-") else v
    except ValueError:
        raise ValueError(f"montant « {texte} » invalide")


def lien_valide(lien):
    """Un lien de justificatif ne peut être qu'une adresse http(s) (jamais javascript:)."""
    lien = (lien or "").strip()
    if lien and not lien.lower().startswith(("http://", "https://")):
        raise ValueError("le lien du justificatif doit commencer par http:// ou https://")
    if len(lien) > 300:
        raise ValueError("lien du justificatif trop long (300 caractères au plus)")
    return lien


def date_texte(texte):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(texte.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"date « {texte} » invalide (jj/mm/aaaa attendu)")


def lire_ecritures(octets, comptes, codes_axe1, codes_axe2, classes_axe2, mvt_existants):
    """Fichier d'écritures (une ligne = un débit ou un crédit, regroupées par Mvt).

    `comptes` : {numéro: axe1 ou None} des comptes déjà au plan.
    Retourne un dict : mouvements, comptes_a_creer, journaux, ignores_axe2.
    Tout est validé avant la moindre écriture en base.
    """
    lignes = lire(octets, ["mvt", "date", "compte", "debit", "credit"])
    erreurs, par_mvt = [], {}
    for n, d in lignes:
        jnl = d.get("jnl") or d.get("journal") or ""
        try:
            if not d["mvt"].isdigit():
                raise ValueError(f"numéro de mouvement « {d['mvt']} » invalide")
            if not jnl:
                raise ValueError("journal (colonne Jnl) manquant")
            deb, cre = montant(d["debit"]), montant(d["credit"])
            if deb < 0 or cre < 0 or (deb and cre) or not (deb or cre):
                raise ValueError("un montant positif au débit OU au crédit")
            if not d["compte"]:
                raise ValueError("compte manquant")
            par_mvt.setdefault(int(d["mvt"]), []).append((n, jnl, date_texte(d["date"]), d, deb, cre))
        except ValueError as e:
            erreurs.append(f"Ligne {n} : {e}")
    if erreurs:
        raise ErreurImport(erreurs)

    mouvements, a_creer, journaux, ignores = [], {}, set(), 0
    for mvt in sorted(par_mvt):
        l = par_mvt[mvt]
        n0 = l[0][0]
        if mvt in mvt_existants:
            erreurs.append(f"Mouvement {mvt} (ligne {n0}) : ce numéro existe déjà dans la base.")
            continue
        if len({x[1] for x in l}) > 1 or len({x[2] for x in l}) > 1:
            erreurs.append(f"Mouvement {mvt} (ligne {n0}) : journal ou date différents selon les lignes.")
            continue
        if len(l) < 2 or sum(x[4] for x in l) != sum(x[5] for x in l):
            erreurs.append(f"Mouvement {mvt} (ligne {n0}) : écriture non équilibrée ou à une seule ligne.")
            continue
        libelle = next((x[3].get("libelle") for x in l if x[3].get("libelle")), "")
        if not libelle:
            erreurs.append(f"Mouvement {mvt} (ligne {n0}) : libellé manquant.")
            continue
        try:
            lien = lien_valide(next((x[3].get("lien") for x in l if x[3].get("lien")), ""))
        except ValueError as e:
            erreurs.append(f"Mouvement {mvt} (ligne {n0}) : {e}.")
            continue
        lg = []
        for n, jnl, dt, d, deb, cre in l:
            num = d["compte"]
            if num not in comptes:
                axe1 = d.get("anal1") or None
                if axe1 and axe1 not in codes_axe1:
                    erreurs.append(f"Ligne {n} : code Axe 1 « {axe1} » inconnu (compte {num}) : importez d'abord les codes Axe 1.")
                    continue
                prev = a_creer.get(num)
                if prev and prev[1] != axe1:
                    erreurs.append(f"Ligne {n} : le compte {num} a des codes Axe 1 différents dans le fichier.")
                    continue
                a_creer[num] = (d.get("libelcompte") or num, axe1)
            axe2 = d.get("anal2") or None
            if axe2:
                if axe2 not in codes_axe2:
                    erreurs.append(f"Ligne {n} : code Axe 2 « {axe2} » inconnu : importez d'abord les codes Axe 2.")
                    continue
                if not num.startswith(tuple(classes_axe2)):
                    axe2 = None
                    ignores += 1
            lg.append((num, deb, cre, axe2))
        else:
            journaux.add(l[0][1])
            mouvements.append({"mvt": mvt, "date": l[0][2], "journal": l[0][1], "libelle": libelle,
                               "lien": lien,
                               "lignes": lg})
    if erreurs:
        raise ErreurImport(erreurs)
    return {"mouvements": mouvements, "comptes_a_creer": a_creer, "journaux": journaux, "ignores_axe2": ignores}
