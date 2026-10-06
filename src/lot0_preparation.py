"""Lot 0 — préparation du classeur ComptaJLC, par édition directe du XML.

    python src/lot0_preparation.py Fusion.xlsm ComptaJLC.xlsm

Le classeur d'entrée n'est jamais modifié. Le XML est édité pièce par pièce :
aucune bibliothèque ne réécrit le classeur (Power Query, commentaires à
thread, validations étendues et graphiques restent intacts). Excel recalcule
tout à l'ouverture (fullCalcOnLoad).

Décisions du trésorier appliquées (26/09/2026) :
 1. T_Ecritures, T_PlanComptable, T_Journaux, T_Axe1, T_Axe2 et T_Prefixes
    ne sont plus rechargées depuis l'ancien logiciel : tables dissociées,
    requêtes et connexions supprimées.
 2. Requête1 lit le chemin du relevé Banque 1 dans Paramètres (relatif au
    dossier de l'application) ; paramètres d'exercice nommés.
 3. Paiements Isracard (Mvt 412 à 416) reclassés : 580000 contre 512000 en
    banque, et charge 600000 contre 580000 en OD (Mvt nouveaux).
 4. Codes Anal2 sans libellé et jamais utilisés supprimés.
 5. T_PlanComptable[Solde] et T_Prefixes[Code suivant] calculés.
 6. Contrôles : RG-04 (période close) et comptes de liaison ; onglet
    Journal des modifications ; Accueil et Compte rendu mis à jour.
"""

import base64
import datetime as dt
import io
import re
import struct
import sys
import urllib.parse
import uuid
import zipfile
from collections import OrderedDict
from xml.sax.saxutils import escape

import openpyxl

AUJOURDHUI = dt.date(2026, 9, 26)
AUTEUR = "Claude Code (Lot 0)"
TABLES_A_DISSOCIER = ["T_Ecritures", "T_PlanComptable", "T_Journaux", "T_Axe1", "T_Axe2", "T_Prefixes"]
COMPTE_VIREMENT, COMPTE_ATTENTE, COMPTE_CHARGE = "580000", "470000", "600000"
DATE_CLOTURE = dt.date(2025, 12, 31)
EXERCICE = (dt.date(2026, 1, 1), dt.date(2026, 12, 31))
RACINE_ONEDRIVE = r"D:\OneDrive"
RELEVE_B1 = r"Releves\tnuot.pdf"
# Libellés fournis par le trésorier pour les codes Anal2 utilisés sans libellé
LIBELLES_AXE2 = {"SOC.005": "ENFANTS MALADES", "SOC.006": "BOURSES", "SOC.007": "AIDE AUX FAMILLES"}

# Styles existants du classeur (cellXfs)
S_DATE, S_MONTANT, S_TEXTE = 1, 2, 3
S_TITRE, S_SECTION, S_ENTETE, S_NOTE, S_LIEN = 4, 70, 9, 24, 41
S_SAISIE, S_SAISIE_DATE, S_SAISIE_ENTIER = 18, 25, 46
S_ORANGE_DATE, S_ORANGE, S_ORANGE_MONTANT, S_ORANGE_TEXTE, S_ORANGE_CALC = 60, 61, 62, 63, 80


def serial(d):
    return (d - dt.date(1899, 12, 30)).days


def col_num(lettres):
    n = 0
    for ch in lettres:
        n = n * 26 + ord(ch) - 64
    return n


def x(texte):
    return escape(str(texte), {'"': "&quot;"})


# ---------------------------------------------------------------- paquet

class Paquet:
    def __init__(self, chemin):
        self.zin = zipfile.ZipFile(chemin)
        self.ordre = [i.filename for i in self.zin.infolist()]
        self.brut = {n: self.zin.read(n) for n in self.ordre}
        self.texte = {}

    def lire(self, nom):
        if nom not in self.texte:
            self.texte[nom] = self.brut[nom].decode("utf-8")
        return self.texte[nom]

    def ecrire(self, nom, contenu):
        if nom not in self.brut and nom not in self.ordre:
            self.ordre.append(nom)
        if isinstance(contenu, bytes):
            self.brut[nom] = contenu
            self.texte.pop(nom, None)
        else:
            self.texte[nom] = contenu

    def supprimer(self, nom):
        self.ordre.remove(nom)
        self.brut.pop(nom, None)
        self.texte.pop(nom, None)

    def enregistrer(self, chemin):
        with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
            for nom in self.ordre:
                data = self.texte[nom].encode("utf-8") if nom in self.texte else self.brut[nom]
                z.writestr(nom, data)


class Chaines:
    """Table des chaînes partagées : réutilise ou ajoute."""

    def __init__(self, paquet):
        self.p = paquet
        s = paquet.lire("xl/sharedStrings.xml")
        self.si = re.findall(r"<si>.*?</si>|<si/>", s, re.S)
        self.index = {}
        for i, e in enumerate(self.si):
            m = re.fullmatch(r'<si><t(?: xml:space="preserve")?>(.*?)</t></si>', e, re.S)
            if m:
                self.index.setdefault(m.group(1), i)
        self.ajouts = 0

    def id(self, texte):
        cle = x(texte)
        if cle not in self.index:
            self.si.append(f'<si><t xml:space="preserve">{cle}</t></si>')
            self.index[cle] = len(self.si) - 1
        self.ajouts += 1
        return self.index[cle]

    def valeur(self, i):
        m = re.search(r"<t[^>]*>(.*?)</t>", self.si[i], re.S)
        return m.group(1) if m else ""

    def enregistrer(self):
        s = self.p.lire("xl/sharedStrings.xml")
        m = re.search(r'<sst [^>]*>', s)
        n = re.search(r' count="(\d+)"', m.group(0))
        tete = s[: m.start()] + (m.group(0).replace(n.group(0), f' count="{int(n.group(1)) + self.ajouts}"') if n else m.group(0))
        tete = re.sub(r'uniqueCount="\d+"', f'uniqueCount="{len(self.si)}"', tete)
        self.p.ecrire("xl/sharedStrings.xml", tete + "".join(self.si) + "</sst>")


class Feuille:
    """Édition des lignes et cellules d'une feuille, le reste du XML intact."""

    RE_LIGNE = re.compile(r'<row r="(\d+)"([^>]*?)(?:/>|>(.*?)</row>)', re.S)
    RE_CELLULE = re.compile(r'<c r="([A-Z]+)(\d+)"[^>]*?(?:/>|>.*?</c>)', re.S)

    def __init__(self, paquet, nom_part):
        self.p, self.nom = paquet, nom_part
        s = paquet.lire(nom_part)
        d, f = s.index("<sheetData"), s.index("</sheetData>")
        ouv = s.index(">", d) + 1
        self.avant, self.apres = s[:ouv], s[f:]
        if s[d:ouv].endswith("/>"):
            self.avant, self.apres = s[:d] + "<sheetData>", "</sheetData>" + s[ouv:]
        self.lignes = OrderedDict()
        for m in self.RE_LIGNE.finditer(s[ouv:f]):
            attrs = re.sub(r'\s*spans="[^"]*"', "", m.group(2))
            cellules = OrderedDict((mm.group(1), mm.group(0)) for mm in self.RE_CELLULE.finditer(m.group(3) or ""))
            self.lignes[int(m.group(1))] = [attrs, cellules]

    def cellule(self, ref):
        col, row = re.fullmatch(r"([A-Z]+)(\d+)", ref).groups()
        ligne = self.lignes.get(int(row))
        return ligne[1].get(col) if ligne else None

    def poser(self, ref, xml_cellule):
        col, row = re.fullmatch(r"([A-Z]+)(\d+)", ref).groups()
        row = int(row)
        if row not in self.lignes:
            self.lignes[row] = [' x14ac:dyDescent="0.2"' if "x14ac" in self.avant else "", OrderedDict()]
        cellules = self.lignes[row][1]
        if xml_cellule is None:
            cellules.pop(col, None)
        else:
            cellules[col] = xml_cellule
        self.lignes[row][1] = OrderedDict(sorted(cellules.items(), key=lambda kv: col_num(kv[0])))

    def supprimer_ligne(self, row):
        self.lignes.pop(row, None)

    def enregistrer(self):
        corps = []
        for r in sorted(self.lignes):
            attrs, cellules = self.lignes[r]
            if cellules:
                cols = [col_num(c) for c in cellules]
                corps.append(f'<row r="{r}" spans="{min(cols)}:{max(cols)}"{attrs}>{"".join(cellules.values())}</row>')
            elif attrs.strip():
                corps.append(f'<row r="{r}"{attrs}/>')
        self.p.ecrire(self.nom, self.avant + "".join(corps) + self.apres)

    def remplacer(self, ancien, nouveau, obligatoire=True):
        # pour les éléments hors sheetData (validations, mises en forme, liens)
        if obligatoire and ancien not in self.apres + self.avant:
            raise ValueError(f"{self.nom} : motif introuvable {ancien[:80]!r}")
        self.avant = self.avant.replace(ancien, nouveau)
        self.apres = self.apres.replace(ancien, nouveau)


def c_texte(ref, ch, texte, s=None):
    st = f' s="{s}"' if s is not None else ""
    return f'<c r="{ref}"{st} t="s"><v>{ch.id(texte)}</v></c>'


def c_nombre(ref, valeur, s=None):
    st = f' s="{s}"' if s is not None else ""
    return f'<c r="{ref}"{st}><v>{valeur}</v></c>'


def c_formule(ref, formule, cache, s=None, dynamique=False):
    st = f' s="{s}"' if s is not None else ""
    t = ' t="str"' if isinstance(cache, str) else ""
    v = "<v/>" if cache in ("", None) else f"<v>{x(cache)}</v>"
    if dynamique:
        return f'<c r="{ref}"{st}{t} cm="1"><f t="array" ref="{ref}">{x(formule)}</f>{v}</c>'
    return f'<c r="{ref}"{st}{t}><f>{x(formule)}</f>{v}</c>'


# ---------------------------------------------------------------- classeur

def feuilles(p):
    wb = p.lire("xl/workbook.xml")
    rels = p.lire("xl/_rels/workbook.xml.rels")
    cibles = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels))
    cibles.update({a: b for b, a in re.findall(r'Target="([^"]+)"[^>]*Id="(rId\d+)"', rels)})
    chemin = lambda c: c[1:] if c.startswith("/") else "xl/" + c
    return {n: chemin(cibles[r]) for n, r in re.findall(r'<sheet name="([^"]+)"[^>]*? r:id="(rId\d+)"\s*/>', wb)}


def tables(p):
    res = {}
    for nom in p.ordre:
        if re.fullmatch(r"xl/tables/table\d+\.xml", nom):
            res[re.search(r' name="([^"]+)"', p.lire(nom)).group(1)] = nom
    return res


def retirer_override(p, part):
    ct = p.lire("[Content_Types].xml")
    p.ecrire("[Content_Types].xml", ct.replace(f'<Override PartName="/{part}" ' + re.search(
        rf'<Override PartName="/{re.escape(part)}" ([^>]*)/>', ct).group(1) + "/>", ""))


def ajouter_override(p, part, type_contenu):
    ct = p.lire("[Content_Types].xml")
    p.ecrire("[Content_Types].xml", ct.replace("</Types>", f'<Override PartName="/{part}" ContentType="{type_contenu}"/></Types>'))


# ---------------------------------------------------------------- 1. dissociation

def lire_mashup(p):
    brut = p.brut["customXml/item1.xml"]
    s = brut.decode("utf-16")
    m = re.search(r">([A-Za-z0-9+/=\s]+)</DataMashup>", s)
    b = base64.b64decode(m.group(1))
    pos, blocs = 4, []
    for _ in range(4):
        n = struct.unpack_from("<I", b, pos)[0]
        blocs.append(b[pos + 4: pos + 4 + n])
        pos += 4 + n
    return s[: m.start(1)], s[m.end(1):], b[:4], blocs


def ecrire_mashup(p, tete, queue, version, blocs):
    b = version + b"".join(struct.pack("<I", len(x_)) + x_ for x_ in blocs)
    p.ecrire("customXml/item1.xml", (tete + base64.b64encode(b).decode() + queue).encode("utf-16"))


def dissocier(p, journal):
    tbl = tables(p)
    wb = p.lire("xl/workbook.xml")
    conn = p.lire("xl/connections.xml")
    requetes = []
    for nom in TABLES_A_DISSOCIER:
        part = tbl[nom]
        rels_part = part.replace("tables/", "tables/_rels/") + ".rels"
        cible = re.search(r'Target="\.\./queryTables/(queryTable\d+\.xml)"', p.lire(rels_part)).group(1)
        qt_part = "xl/queryTables/" + cible
        qt = p.lire(qt_part)
        nom_qt = re.search(r' name="([^"]+)"', qt).group(1)
        cid = re.search(r' connectionId="(\d+)"', qt).group(1)
        # table : n'est plus une table de requête
        t = p.lire(part)
        t = t.replace(' tableType="queryTable"', "")
        t = re.sub(r' uniqueName="[^"]*"', "", t)
        t = re.sub(r' queryTableFieldId="\d+"', "", t)
        p.ecrire(part, t)
        for q in (rels_part, qt_part):
            if q == qt_part:
                retirer_override(p, qt_part)
            p.supprimer(q)
        # nom défini DonnéesExternes_n
        wb = re.sub(rf'<definedName name="{re.escape(nom_qt)}"[^>]*>[^<]*</definedName>', "", wb)
        # connexion
        m = re.search(rf'<connection id="{cid}" .*?</connection>', conn, re.S)
        requetes.append(re.search(r"Location=([^;]+);", m.group(0)).group(1))
        conn = conn.replace(m.group(0), "")
        journal.append(("Dissociation", nom, f"requête « {requetes[-1]} »", "table simple"))
    p.ecrire("xl/workbook.xml", wb)
    p.ecrire("xl/connections.xml", conn)

    # Requêtes supprimées du DataMashup ; Requête1 lit son chemin dans Paramètres
    tete, queue, version, (pkg, perm, meta, bind) = lire_mashup(p)
    zin = zipfile.ZipFile(io.BytesIO(pkg))
    sortie = io.BytesIO()
    with zipfile.ZipFile(sortie, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "Formulas/Section1.m":
                m_code = data.decode("utf-8-sig")
                bom = data.startswith(b"\xef\xbb\xbf")
                for r in requetes:
                    m_code, n = re.subn(rf'\r?\n\r?\nshared #"{re.escape(r)}" = .*?(?=\r?\n\r?\nshared |\Z)', "", m_code, flags=re.S)
                    assert n == 1, r
                ancien = 'Chemin   = "D:\\OneDrive\\Compta Bnei Brith\\tnuot.pdf",'
                assert ancien in m_code
                m_code = m_code.replace(ancien, 'Chemin   = Excel.CurrentWorkbook(){[Name="CheminReleveB1"]}[Content]{0}[Column1],')
                data = (b"\xef\xbb\xbf" if bom else b"") + m_code.encode("utf-8")
            zout.writestr(info, data)
    mv, ml = struct.unpack_from("<II", meta, 0)
    mx, reste = meta[8: 8 + ml], meta[8 + ml:]
    bom = mx.startswith(b"\xef\xbb\xbf")
    xml = mx.decode("utf-8-sig")
    for r in requetes:
        chemin = "Section1/" + urllib.parse.quote(r, safe="")
        xml, n = re.subn(rf"<Item><ItemLocation><ItemType>Formula</ItemType><ItemPath>{re.escape(chemin)}(?:/[^<]*)?</ItemPath>.*?</Item>", "", xml, flags=re.S)
        assert n >= 1, r
    mx = (b"\xef\xbb\xbf" if bom else b"") + xml.encode("utf-8")
    meta = struct.pack("<II", mv, len(mx)) + mx + reste
    ecrire_mashup(p, tete, queue, version, [sortie.getvalue(), perm, meta, bind])
    journal.append(("Chemin relatif", "Requête1", r"D:\OneDrive\Compta Bnei Brith\tnuot.pdf", "Paramètres!B3 (CheminReleveB1)"))


# ---------------------------------------------------------------- 2. paramètres

def parametres(p, ch, f, journal):
    fe = Feuille(p, f["Paramètres"])
    dossier = RACINE_ONEDRIVE + r"\Applications\ComptaJLC"
    lignes = [
        (5, "Début de l'exercice ouvert", "date", EXERCICE[0], "P_DebutExercice", "Exercice 2026."),
        (6, "Fin de l'exercice ouvert", "date", EXERCICE[1], "P_FinExercice", ""),
        (7, "Période close jusqu'au (inclus)", "date", DATE_CLOTURE, "P_DateCloture",
         "Exercice court du 25/10/2025 au 31/12/2025 : aucune écriture nouvelle à cette date ou avant (RG-04)."),
        (8, "Dernier Mvt de la période close", "entier", None, "P_DernierMvtClos",
         "Mouvement le plus récent au moment de la clôture : un Mvt supérieur daté dans la période close est une anomalie."),
        (9, "Compte de virement interne", "texte", COMPTE_VIREMENT, "P_CompteVirement",
         "Virements entre banques et paiements carte Isracard (décision Q2)."),
        (10, "Compte d'attente", "texte", COMPTE_ATTENTE, "P_CompteAttente",
         "Opérations en attente d'éclaircissement (décision Q3)."),
    ]
    fe.poser("D3", c_texte("D3", ch, "Paramètres de l'application", S_SECTION))
    for col, t in zip("DEF", ("Paramètre", "Valeur", "Commentaire")):
        fe.poser(f"{col}4", c_texte(f"{col}4", ch, t, S_ENTETE))
    noms = {}
    for r, lib, typ, val, nom, com in lignes:
        fe.poser(f"D{r}", c_texte(f"D{r}", ch, lib))
        if typ == "date":
            fe.poser(f"E{r}", c_nombre(f"E{r}", serial(val), S_SAISIE_DATE))
        elif typ == "entier":
            fe.poser(f"E{r}", c_nombre(f"E{r}", "{DERNIER_MVT}", S_SAISIE_ENTIER))
        else:
            fe.poser(f"E{r}", c_texte(f"E{r}", ch, val, S_SAISIE))
        if com:
            fe.poser(f"F{r}", c_texte(f"F{r}", ch, com, S_NOTE))
        noms[nom] = f"Paramètres!$E${r}"
    fe.poser("D12", c_texte("D12", ch, "Emplacement des fichiers", S_SECTION))
    fe.poser("D13", c_texte("D13", ch, "Dossier du classeur (détecté)"))
    fe.poser("E13", c_formule("E13", 'IFERROR(LEFT(CELL("filename",$A$1),FIND("[",CELL("filename",$A$1))-2),"")', dossier, S_TEXTE))
    fe.poser("F13", c_texte("F13", ch, "Calculé. Une adresse https:// signifie que le classeur est ouvert depuis OneDrive : la ligne suivante s'applique.", S_NOTE))
    fe.poser("D14", c_texte("D14", ch, "Racine OneDrive de ce poste"))
    fe.poser("E14", c_texte("E14", ch, RACINE_ONEDRIVE, S_SAISIE))
    fe.poser("F14", c_texte("F14", ch, "Sert seulement si le dossier détecté commence par https:// ; à adapter sur un autre poste.", S_NOTE))
    fe.poser("D15", c_texte("D15", ch, "Dossier de l'application"))
    fe.poser("E15", c_formule("E15", 'IF(LEFT(E13,4)="http",E14&SUBSTITUTE(SUBSTITUTE(MID(E13,FIND("/",E13,FIND("/",E13,9)+1),999),"/","\\"),"%20"," "),E13)', dossier, S_TEXTE))
    fe.poser("F15", c_texte("F15", ch, "Calculé : racine de tous les chemins relatifs.", S_NOTE))
    fe.poser("D16", c_texte("D16", ch, "Relevé Banque 1 (chemin relatif)"))
    fe.poser("E16", c_texte("E16", ch, RELEVE_B1, S_SAISIE))
    fe.poser("F16", c_texte("F16", ch, "Relatif au dossier de l'application ; lu par la requête Requête1 via B3.", S_NOTE))
    noms["P_Dossier"] = "Paramètres!$E$15"
    noms["P_ReleveB1"] = "Paramètres!$E$16"
    # B3 = CheminReleveB1, désormais calculé
    fe.poser("B3", c_formule("B3", 'P_Dossier&"\\"&P_ReleveB1', dossier + "\\" + RELEVE_B1, S_TEXTE))
    fe.poser("A4", c_texte("A4", ch, "Calculé à partir de l'emplacement des fichiers (E13:E16) : déposer le relevé téléchargé dans le sous-dossier Releves de l'application.", S_NOTE))
    fe.remplacer('<col min="2" max="2" width="66.6640625" customWidth="1"/></cols>',
                 '<col min="2" max="2" width="66.6640625" customWidth="1"/><col min="4" max="4" width="30" customWidth="1"/>'
                 '<col min="5" max="5" width="38" customWidth="1"/><col min="6" max="6" width="90" customWidth="1"/></cols>')
    journal.append(("Paramètres", "Paramètres!D3:F16", "", "exercice 2026, clôture au 31/12/2025, comptes 580000 / 470000, dossier et relevé relatifs"))
    return fe, noms


def ajouter_noms(p, noms):
    wb = p.lire("xl/workbook.xml")
    m = re.search(r"<definedNames>(.*?)</definedNames>", wb, re.S)
    existants = re.findall(r"<definedName .*?</definedName>", m.group(1), re.S)
    for n, ref in noms.items():
        existants.append(f'<definedName name="{n}">{x(ref)}</definedName>')
    cle = lambda e: (re.search(r'name="([^"]+)"', e).group(1).lower(), re.search(r'localSheetId="(\d+)"', e) is None)
    p.ecrire("xl/workbook.xml", wb.replace(m.group(0), "<definedNames>" + "".join(sorted(existants, key=cle)) + "</definedNames>"))


# ---------------------------------------------------------------- 3. Isracard

class Commentaires:
    """Commentaires à thread de la feuille Écritures (+ copies héritées et VML)."""

    AVERT = ("[Commentaire à thread]\n\nVotre version d’Excel vous permet de lire ce commentaire à thread. "
             "Toutefois, les modifications qui y sont apportées seront supprimées si le fichier est ouvert dans une "
             "version plus récente d’Excel. En savoir plus : https://go.microsoft.com/fwlink/?linkid=870924\n\n")

    def __init__(self, p, rels_feuille):
        self.p = p
        rels = p.lire(rels_feuille)
        self.legacy = "xl/" + re.search(r'Target="\.\./(comments\d+\.xml)"', rels).group(1)
        self.fil = "xl/" + re.search(r'Target="\.\./(threadedComments/threadedComment\d+\.xml)"', rels).group(1)
        self.vml = "xl/" + re.search(r'Target="\.\./(drawings/vmlDrawing\d+\.vml)"', rels).group(1)
        self.personne = "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, "comptajlc/claude-code")).upper() + "}"
        pers = p.lire("xl/persons/person.xml")
        if self.personne not in pers:
            p.ecrire("xl/persons/person.xml", pers.replace(
                "</personList>", f'<person displayName="Claude Code" id="{self.personne}" userId="Claude Code" providerId="None"/></personList>'))

    @staticmethod
    def guid(graine):
        return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, "comptajlc/" + graine)).upper() + "}"

    def _heure(self, i):
        return f"{AUJOURDHUI.isoformat()}T12:{i // 60:02d}:{i % 60:02d}.00"

    def repondre(self, ref, texte, i):
        fil = self.p.lire(self.fil)
        parent = re.search(rf'<threadedComment ref="{ref}" [^>]*id="(\{{[^}}]+\}})"', fil).group(1)
        # la réponse se place après le dernier message du fil
        fins = [m.end() for m in re.finditer(rf'<threadedComment ref="{ref}" .*?</threadedComment>', fil, re.S)]
        rep = (f'<threadedComment ref="{ref}" dT="{self._heure(i)}" personId="{self.personne}" '
               f'id="{self.guid(ref + "/reponse")}" parentId="{parent}"><text>{x(texte)}</text></threadedComment>')
        self.p.ecrire(self.fil, fil[: fins[-1]] + rep + fil[fins[-1]:])
        leg = self.p.lire(self.legacy)
        m = re.search(rf'(<comment ref="{ref}" .*?<t>)(.*?)(</t>)', leg, re.S)
        self.p.ecrire(self.legacy, leg.replace(m.group(0), m.group(1) + m.group(2) + x("\nRéponse :\n    " + texte) + m.group(3)))

    def ajouter(self, ref, texte, i):
        gid = self.guid(ref)
        fil = self.p.lire(self.fil)
        self.p.ecrire(self.fil, fil.replace("</ThreadedComments>",
            f'<threadedComment ref="{ref}" dT="{self._heure(i)}" personId="{self.personne}" id="{gid}"><text>{x(texte)}</text></threadedComment></ThreadedComments>'))
        leg = self.p.lire(self.legacy)
        n_auteurs = len(re.findall(r"<author>", leg))
        leg = leg.replace("</authors>", f"<author>tc={gid}</author></authors>")
        uid = gid
        leg = leg.replace("</commentList>", f'<comment ref="{ref}" authorId="{n_auteurs}" shapeId="0" xr:uid="{uid}"><text><t>'
                          + x(self.AVERT + "Commentaire :\n    " + texte) + "</t></text></comment></commentList>")
        self.p.ecrire(self.legacy, leg)
        vml = self.p.lire(self.vml)
        ids = [int(v) for v in re.findall(r'id="_x0000_s(\d+)"', vml)]
        zs = [int(v) for v in re.findall(r"z-index:(\d+)", vml)]
        r0 = int(re.fullmatch(r"[A-Z]+(\d+)", ref).group(1)) - 1
        forme = f"""<v:shape id="_x0000_s{max(ids) + 1}" type="#_x0000_t202" style='position:absolute;
  margin-left:51.75pt;margin-top:{18296.25 + (r0 - 1525) * 12:.2f}pt;width:326.25pt;height:240.75pt;
  z-index:{max(zs) + 1};visibility:hidden' fillcolor="infoBackground [80]" strokecolor="none [81]"
  o:insetmode="auto">
  <v:fill color2="infoBackground [80]"/>
  <v:shadow color="none [81]" obscured="t"/>
  <v:path o:connecttype="none"/>
  <v:textbox style='mso-direction-alt:auto'>
   <div style='text-align:left;direction:ltr'></div>
  </v:textbox>
  <x:ClientData ObjectType="Note">
   <x:MoveWithCells/>
   <x:SizeWithCells/>
   <x:Anchor>
    1, 6, {r0 - 1}, 11, 6, 19, {r0 + 19}, 12</x:Anchor>
   <x:AutoFill>False</x:AutoFill>
   <x:Row>{r0}</x:Row>
   <x:Column>0</x:Column>
  </x:ClientData>
 </v:shape>"""
        self.p.ecrire(self.vml, vml.replace("</xml>", forme + "</xml>"))


def isracard(p, ch, f, valeurs, journal):
    """valeurs : lignes de T_Ecritures lues par openpyxl (listes, ligne 2 = index 0)."""
    part = f["Écritures"]
    fe = Feuille(p, part)
    plan = valeurs["plan"]
    axe1 = valeurs["axe1"]
    ecr = valeurs["ecritures"]
    n = len(ecr) + 1  # dernière ligne de la table
    idx = {h: i for i, h in enumerate(valeurs["entetes"])}
    mvts = sorted({l[idx["Mvt"]] for l in ecr if l[idx["Libellé"]] == "PAIEMENT CARTE ISRACARD - RELEVE BANQUE 1"})
    assert mvts == [412, 413, 414, 415, 416], mvts
    modele = {c: fe.cellule(f"{c}{n}") for c in "FKNOPQR"}
    for c, cel in modele.items():
        assert cel and "<f" in cel, c
    formules = {c: re.search(r"<f[^>]*>(.*?)</f>", cel, re.S).group(1) for c, cel in modele.items()}
    piece = max(l[idx["Pièce"]] for l in ecr)
    mvt_max = max(l[idx["Mvt"]] for l in ecr)
    com = Commentaires(p, part.replace("worksheets/", "worksheets/_rels/") + ".rels")

    def caches(compte, anal2):
        lib, a1 = plan[compte][0], plan[compte][1]
        return {"F": lib, "K": a1, "N": compte[0], "O": "", "P": axe1.get(a1, "Code introuvable"),
                "Q": valeurs["axe2"][anal2][0], "R": valeurs["axe2"][anal2][1]}

    def formule_cellule(ref_col, r, cache, s):
        f_ = formules[ref_col]
        if ref_col == "O":
            return f'<c r="O{r}" s="{s}" t="str" cm="1"><f t="array" ref="O{r}">{f_}</f><v/></c>'
        t = ' t="str"' if isinstance(cache, str) else ""
        return f'<c r="{ref_col}{r}" s="{s}"{t}><f>{f_}</f><v>{x(cache)}</v></c>'

    r = n
    for i, mvt in enumerate(mvts):
        lignes = [(k + 2, l) for k, l in enumerate(ecr) if l[idx["Mvt"]] == mvt]
        (r_charge, charge), = [(k, l) for k, l in lignes if str(l[idx["Compte"]]) == COMPTE_CHARGE]
        montant = charge[idx["Débit"]]
        date, anal2 = charge[idx["Date"]], charge[idx["Anal2"]]
        # a) la ligne 600000 du Mvt bancaire passe en 580000
        fe.poser(f"E{r_charge}", c_texte(f"E{r_charge}", ch, COMPTE_VIREMENT, S_ORANGE_TEXTE))
        cc = caches(COMPTE_VIREMENT, anal2)
        for c in "FKN":
            fe.poser(f"{c}{r_charge}", formule_cellule(c, r_charge, cc[c], S_ORANGE))
        fe.poser(f"P{r_charge}", formule_cellule("P", r_charge, cc["P"], S_ORANGE_CALC))
        journal.append(("Reclassement", f"Mvt {mvt} (ligne {r_charge})", f"{COMPTE_CHARGE} au débit", f"{COMPTE_VIREMENT} au débit"))
        # b) nouveau Mvt en OD : charge 600000 contre 580000
        piece += 1
        mvt_max += 1
        libelle = f"CHARGES CARTE ISRACARD - PRELEVEMENT MVT {mvt}"
        for compte, debit, credit in ((COMPTE_CHARGE, montant, 0), (COMPTE_VIREMENT, 0, montant)):
            r += 1
            cc = caches(compte, anal2)
            fe.poser(f"A{r}", c_nombre(f"A{r}", serial(date.date()), S_ORANGE_DATE))
            fe.poser(f"B{r}", c_texte(f"B{r}", ch, "OD", S_ORANGE))
            fe.poser(f"C{r}", c_nombre(f"C{r}", mvt_max, S_ORANGE))
            fe.poser(f"D{r}", c_nombre(f"D{r}", piece, S_ORANGE))
            fe.poser(f"E{r}", c_texte(f"E{r}", ch, compte, S_ORANGE_TEXTE))
            fe.poser(f"G{r}", c_texte(f"G{r}", ch, libelle, S_ORANGE))
            fe.poser(f"H{r}", c_nombre(f"H{r}", debit, S_ORANGE_MONTANT))
            fe.poser(f"I{r}", c_nombre(f"I{r}", credit, S_ORANGE_MONTANT))
            fe.poser(f"J{r}", c_nombre(f"J{r}", 0, S_ORANGE_MONTANT))
            fe.poser(f"L{r}", c_texte(f"L{r}", ch, anal2, S_ORANGE))
            fe.poser(f"M{r}", f'<c r="M{r}" s="{S_ORANGE}"/>')
            for c in "FKNO":
                fe.poser(f"{c}{r}", formule_cellule(c, r, cc[c], S_ORANGE))
            for c in "PQR":
                fe.poser(f"{c}{r}", formule_cellule(c, r, cc[c], S_ORANGE_CALC))
        journal.append(("Ajout", f"Mvt {mvt_max} (OD, pièce {piece}, lignes {r - 1}-{r})", "",
                        f"{COMPTE_CHARGE} D / {COMPTE_VIREMENT} C {montant:.2f} (charge Isracard prélevée par le Mvt {mvt})"))
        com.repondre(f"A{lignes[0][0]}",
                     f"Reclassé le 26/09/2026 (Lot 0, décision du trésorier) : la ligne {COMPTE_CHARGE} devient {COMPTE_VIREMENT} "
                     f"(virement interne). La charge {COMPTE_CHARGE} est portée par le Mvt {mvt_max} (journal OD).", i)
        com.ajouter(f"A{r - 1}",
                    f"Écriture ajoutée le 26/09/2026 (Lot 0, décision Q2) : charge des paiements carte Isracard prélevés par le "
                    f"Mvt {mvt}, passée par le compte de virement interne {COMPTE_VIREMENT}. Détail par compte de charge à "
                    f"affiner avec les relevés Isracard.", 10 + i)
    # table, validations, mise en forme, dimension
    t = tables(p)["T_Ecritures"]
    tx = p.lire(t).replace(f'ref="A1:R{n}"', f'ref="A1:R{r}"')
    p.ecrire(t, tx)
    for motif in ("B2:B", "E2:E", "H2:I", "L2:L", "O2:R", "R2:R"):
        fe.remplacer(f"{motif}{n}", f"{motif}{r}")
    fe.remplacer(f'<dimension ref="A1:V{n}"/>', f'<dimension ref="A1:V{r}"/>')
    fe.enregistrer()
    return mvt_max, r


# ---------------------------------------------------------------- 4 & 5. référentiels

def referentiels(p, ch, f, valeurs, ecritures_finales, journal):
    # T_Axe2 : codes sans libellé et jamais utilisés
    fe = Feuille(p, f["Axe 2 - Anal2"])
    utilises = {l[1] for l in ecritures_finales}
    lignes = []
    for r in range(2, len(valeurs["axe2_lignes"]) + 2):
        code, lib, _ = valeurs["axe2_lignes"][r - 2]
        garder = bool(lib) or code in utilises
        if not garder:
            journal.append(("Suppression", f"T_Axe2 {code}", "sans libellé, jamais utilisé", ""))
        lignes.append((garder, {c: fe.cellule(f"{c}{r}") for c in "ABC"}))
    gardes = [cel for g, cel in lignes if g]
    fin_avant = len(lignes) + 1
    for r in range(2, fin_avant + 1):
        for c in "ABC":
            fe.poser(f"{c}{r}", None)
    for k, cel in enumerate(gardes):
        r = k + 2
        for c in "ABC":
            fe.poser(f"{c}{r}", re.sub(r'r="[A-Z]+\d+"', f'r="{c}{r}"', cel[c], count=1))
        code = ch.valeur(int(re.search(r"<v>(\d+)</v>", cel["A"]).group(1)))
        if code in LIBELLES_AXE2:
            fe.poser(f"B{r}", c_texte(f"B{r}", ch, LIBELLES_AXE2[code]))
            journal.append(("Libellé", f"T_Axe2 {code}", "vide", LIBELLES_AXE2[code]))
    for r in range(len(gardes) + 2, fin_avant + 1):
        if r in fe.lignes and not fe.lignes[r][1]:
            fe.supprimer_ligne(r)
    fin = len(gardes) + 1
    fe.remplacer(f'<dimension ref="A1:G{fin_avant}"/>', f'<dimension ref="A1:G{fin}"/>')
    fe.enregistrer()
    t = tables(p)["T_Axe2"]
    tx = p.lire(t).replace(f'ref="A1:C{fin_avant}"', f'ref="A1:C{fin}"')
    tx = re.sub(r"<sortState .*?</sortState>", "", tx, flags=re.S)
    p.ecrire(t, tx)
    codes_axe2 = [re.search(r"<v>(\d+)</v>", cel["A"]).group(1) for cel in gardes]
    codes_axe2 = [ch.valeur(int(i)) for i in codes_axe2]

    # T_PlanComptable[Solde] calculé
    fe = Feuille(p, f["Plan comptable"])
    t = tables(p)["T_PlanComptable"]
    ref_fin = int(re.search(r'ref="A1:G(\d+)"', p.lire(t)).group(1))
    formule = ("SUMIFS(T_Ecritures[Débit],T_Ecritures[Compte],T_PlanComptable[[#This Row],[Compte]])"
               "-SUMIFS(T_Ecritures[Crédit],T_Ecritures[Compte],T_PlanComptable[[#This Row],[Compte]])")
    soldes = {}
    for compte, _, _, d, c in ecritures_finales:
        soldes[compte] = soldes.get(compte, 0) + d - c
    for r in range(2, ref_fin + 1):
        compte = ch.valeur(int(re.search(r"<v>(\d+)</v>", fe.cellule(f"A{r}")).group(1)))
        ancien = fe.cellule(f"G{r}")
        s = re.search(r' s="(\d+)"', ancien).group(1) if ancien and ' s="' in ancien else None
        fe.poser(f"G{r}", c_formule(f"G{r}", formule, round(soldes.get(compte, 0), 2), s))
    fe.enregistrer()
    tx = p.lire(t)
    tx = re.sub(r'(<tableColumn [^>]*name="Solde"[^>]*?)(/>|>)',
                lambda m: m.group(1) + "><calculatedColumnFormula>" + x(formule) + "</calculatedColumnFormula></tableColumn>"
                if m.group(2) == "/>" else m.group(0), tx)
    p.ecrire(t, tx)
    journal.append(("Formule", "T_PlanComptable[Solde]", "valeur de l'ancien logiciel", "solde calculé depuis T_Ecritures"))

    # T_Prefixes[Code suivant] calculé
    fe = Feuille(p, f["Préfixes"])
    t = tables(p)["T_Prefixes"]
    ref_fin = int(re.search(r'ref="A1:D(\d+)"', p.lire(t)).group(1))
    formule = ('_xlfn.LET(_xlpm.p,T_Prefixes[[#This Row],[Préfixe]],'
               '_xlpm.c,IF(T_Prefixes[[#This Row],[Axe]]=1,T_Axe1[Code],T_Axe2[Code]),'
               '_xlpm.s,MID(_xlfn._xlws.FILTER(_xlpm.c,LEFT(_xlpm.c,LEN(_xlpm.p))=_xlpm.p,_xlpm.p),LEN(_xlpm.p)+1,10),'
               '_xlpm.n,IFERROR(--_xlpm.s,0),'
               '_xlpm.w,MAX(IF(T_Prefixes[[#This Row],[Axe]]=2,3,1),IFERROR(LEN(_xlpm.s)*ISNUMBER(--_xlpm.s),0)),'
               '_xlpm.p&TEXT(MAX(_xlpm.n)+1,REPT("0",_xlpm.w)))')
    codes = {1: [a for a in valeurs["axe1"]], 2: codes_axe2}
    for r in range(2, ref_fin + 1):
        pref = ch.valeur(int(re.search(r"<v>(\d+)</v>", fe.cellule(f"A{r}")).group(1)))
        axe = int(re.search(r"<v>(\d+)</v>", fe.cellule(f"B{r}")).group(1))
        suffixes = [c[len(pref):] for c in codes[axe] if c.startswith(pref)]
        nums = [int(s_) for s_ in suffixes if s_.isdigit()]
        w = max([3 if axe == 2 else 1] + [len(s_) for s_ in suffixes if s_.isdigit()])
        cache = pref + str(max(nums, default=0) + 1).zfill(w)
        ancien = fe.cellule(f"D{r}")
        s = re.search(r' s="(\d+)"', ancien).group(1) if ancien and ' s="' in ancien else None
        avant = ch.valeur(int(re.search(r"<v>(\d+)</v>", ancien).group(1)))
        fe.poser(f"D{r}", c_formule(f"D{r}", formule, cache, s, dynamique=True))
        if avant != cache:
            journal.append(("Formule", f"T_Prefixes {pref} Code suivant", avant, cache))
    fe.enregistrer()
    tx = p.lire(t)
    tx = re.sub(r'(<tableColumn [^>]*name="Code suivant"[^>]*?)(/>|>)',
                lambda m: m.group(1) + '><calculatedColumnFormula array="1">' + x(formule) + "</calculatedColumnFormula></tableColumn>"
                if m.group(2) == "/>" else m.group(0), tx)
    p.ecrire(t, tx)


# ---------------------------------------------------------------- 6. contrôles, journal, accueil, compte rendu

def controles(p, ch, f, soldes, journal):
    fe = Feuille(p, f["Contrôles"])
    fe.poser("A18", c_texte("A18", ch, "Écritures nouvelles datées dans la période close (RG-04)"))
    fe.poser("B18", c_formule("B18", 'COUNTIFS(T_Ecritures[Date],"<="&P_DateCloture,T_Ecritures[Mvt],">"&P_DernierMvtClos,T_Ecritures[Jnl],"<>AN")', 0, 16))
    fe.poser("C18", c_formule("C18", 'IF(B18=0,"OK","Anomalie")', "OK", 15))
    fe.poser("M20", c_texte("M20", ch, "Comptes de liaison (solde attendu : 0)", 8))
    for col, t in zip("MNOP", ("Compte", "Intitulé", "Solde écritures", "Statut")):
        fe.poser(f"{col}21", c_texte(f"{col}21", ch, t, S_ENTETE))
    for r, nom, compte in ((22, "P_CompteVirement", COMPTE_VIREMENT), (23, "P_CompteAttente", COMPTE_ATTENTE)):
        solde = round(soldes.get(compte, 0), 2)
        fe.poser(f"M{r}", c_formule(f"M{r}", nom, compte))
        fe.poser(f"N{r}", c_formule(f"N{r}", f'IFERROR(INDEX(T_PlanComptable[Libellé compte],MATCH(M{r},T_PlanComptable[Compte],0)),"Compte inconnu")', {COMPTE_VIREMENT: "VIREMENT", COMPTE_ATTENTE: "CPTES D'ATTENTE"}[compte]))
        fe.poser(f"O{r}", c_formule(f"O{r}", f"SUMIFS(T_Ecritures[Débit],T_Ecritures[Compte],M{r})-SUMIFS(T_Ecritures[Crédit],T_Ecritures[Compte],M{r})", solde, S_MONTANT))
        fe.poser(f"P{r}", c_formule(f"P{r}", f'IF(ROUND(O{r},2)=0,"Soldé","À analyser")', "Soldé" if solde == 0 else "À analyser"))
    fe.enregistrer()
    journal.append(("Contrôle", "Contrôles!A18:C18", "solde du plan ≠ solde des écritures", "RG-04 : écritures nouvelles dans la période close"))
    journal.append(("Contrôle", "Contrôles!M20:P23", "comptes en écart plan / écritures", "comptes de liaison 580000 et 470000"))


def onglet_journal(p, ch, journal):
    wb = p.lire("xl/workbook.xml")
    rels = p.lire("xl/_rels/workbook.xml.rels")
    n_feuille = max(int(v) for v in re.findall(r"worksheets/sheet(\d+)\.xml", rels)) + 1
    rid = "rId" + str(max(int(v) for v in re.findall(r'Id="rId(\d+)"', rels)) + 1)
    sheet_id = max(int(v) for v in re.findall(r'sheetId="(\d+)"', wb)) + 1
    n_table = max(int(v) for v in re.findall(r"xl/tables/table(\d+)\.xml", " ".join(p.ordre))) + 1
    table_id = max(int(re.search(r' id="(\d+)"', p.lire(t)).group(1)) for t in tables(p).values()) + 1
    nom = "Journal des modifications"
    entetes = ["Date", "Auteur", "Lot", "Action", "Objet", "Avant", "Après"]
    lignes = []
    lignes.append(f'<row r="1" spans="1:9" ht="21" x14ac:dyDescent="0.35">{c_texte("A1", ch, nom, S_TITRE)}'
                  f'{c_texte("I1", ch, "← Accueil", S_LIEN)}</row>')
    lignes.append(f'<row r="2" spans="1:1" x14ac:dyDescent="0.2">{c_texte("A2", ch, "Toute modification des écritures, des référentiels ou de la structure du classeur : une ligne par changement (cahier des charges §9). Pour ajouter une ligne, saisir sous la table.", S_NOTE)}</row>')
    lignes.append('<row r="4" spans="1:7" x14ac:dyDescent="0.2">' + "".join(
        c_texte(f"{chr(65 + i)}4", ch, h) for i, h in enumerate(entetes)) + "</row>")
    for k, (action, objet, avant, apres) in enumerate(journal):
        r = 5 + k
        lignes.append(f'<row r="{r}" spans="1:7" x14ac:dyDescent="0.2">'
                      + c_nombre(f"A{r}", serial(AUJOURDHUI), S_DATE) + c_texte(f"B{r}", ch, AUTEUR)
                      + c_texte(f"C{r}", ch, "Lot 0") + c_texte(f"D{r}", ch, action) + c_texte(f"E{r}", ch, objet)
                      + (c_texte(f"F{r}", ch, avant) if avant else "") + (c_texte(f"G{r}", ch, apres) if apres else "") + "</row>")
    fin = 4 + len(journal)
    feuille = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
               'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="x14ac" '
               'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac">'
               f'<dimension ref="A1:I{fin}"/><sheetViews><sheetView showGridLines="0" workbookViewId="0">'
               '<pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/>'
               '<selection pane="bottomLeft" activeCell="A5" sqref="A5"/></sheetView></sheetViews>'
               '<sheetFormatPr baseColWidth="10" defaultRowHeight="12" x14ac:dyDescent="0.2"/>'
               '<cols><col min="1" max="1" width="11" customWidth="1"/><col min="2" max="2" width="20" customWidth="1"/>'
               '<col min="3" max="3" width="7" customWidth="1"/><col min="4" max="4" width="15" customWidth="1"/>'
               '<col min="5" max="5" width="42" customWidth="1"/><col min="6" max="6" width="38" customWidth="1"/>'
               '<col min="7" max="7" width="70" customWidth="1"/></cols>'
               f'<sheetData>{"".join(lignes)}</sheetData>'
               '<hyperlinks><hyperlink ref="I1" location="\'Accueil\'!A1" tooltip="Retour au menu" display="← Accueil"/></hyperlinks>'
               '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
               '<tableParts count="1"><tablePart r:id="rId1"/></tableParts></worksheet>')
    part = f"xl/worksheets/sheet{n_feuille}.xml"
    p.ecrire(part, feuille)
    p.ecrire(f"xl/worksheets/_rels/sheet{n_feuille}.xml.rels",
             '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             f'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table{n_table}.xml"/>'
             '</Relationships>')
    cols = "".join(f'<tableColumn id="{i + 1}" name="{h}"/>' for i, h in enumerate(entetes))
    p.ecrire(f"xl/tables/table{n_table}.xml",
             '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
             f'<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" id="{table_id}" name="T_Journal" '
             f'displayName="T_Journal" ref="A4:G{fin}" totalsRowShown="0"><autoFilter ref="A4:G{fin}"/>'
             f'<tableColumns count="{len(entetes)}">{cols}</tableColumns>'
             '<tableStyleInfo name="TableStyleLight9" showFirstColumn="0" showLastColumn="0" showRowStripes="1" showColumnStripes="0"/></table>')
    ajouter_override(p, part, "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    ajouter_override(p, f"xl/tables/table{n_table}.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml")
    p.ecrire("xl/_rels/workbook.xml.rels", rels.replace("</Relationships>",
             f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{n_feuille}.xml"/></Relationships>'))
    # onglet placé juste avant Feuil1 (dernier onglet)
    p.ecrire("xl/workbook.xml", wb.replace('<sheet name="Feuil1"', f'<sheet name="{nom}" sheetId="{sheet_id}" r:id="{rid}"/><sheet name="Feuil1"'))
    assert 'localSheetId="21"' not in wb
    return nom


def accueil_et_compte_rendu(p, ch, f, nom_journal, dernier_mvt):
    fe = Feuille(p, f["Accueil"])
    fe.poser("B33", c_texte("B33", ch, "→ " + nom_journal, 35))
    fe.poser("C33", c_texte("C33", ch, "Traçabilité : date, auteur et objet de chaque modification", 36))
    fe.remplacer("</hyperlinks>", f'<hyperlink ref="B33" location="\'{nom_journal}\'!A1" display="→ {nom_journal}"/></hyperlinks>')
    fe.remplacer('<dimension ref="A1:E32"/>', '<dimension ref="A1:E33"/>')
    fe.enregistrer()

    fe = Feuille(p, f["Écritures à passer"])
    ancien = fe.cellule("A2")
    s = re.search(r' s="(\d+)"', ancien).group(1) if ' s="' in ancien else None
    fe.poser("A2", c_texte("A2", ch, "Écritures intégrées le 26/09/2026 dans l'onglet Écritures (lignes 1526 à 1535, fond orangé et commentaire), "
                                       "puis reclassées le même jour (Lot 0) : 580000 contre 512000 en banque, charge 600000 contre 580000 "
                                       "en OD (Mvt 417 à 421). Voir Journal des modifications.", s))
    fe.enregistrer()

    fe = Feuille(p, f["Compte rendu"])
    textes = {
        "C34": "Fait : écritures Isracard intégrées puis reclassées (Lot 0) : 580000 contre 512000 en banque, charge 600000 contre 580000 en OD (Mvt 417 à 421).",
        "C39": "Clôture de l'exercice court au 31/12/2025 (Lot 4) : à-nouveaux, affectation du résultat ; la période est déjà verrouillée (RG-04).",
        "C44": "Saisir en bas de la table Écritures : les formules et contrôles s'étendent automatiquement. Numéroter Mvt = MAX(Mvt)+1, Pièce = MAX(Pièce)+1.",
        "C46": "Enregistrer le PDF téléchargé sous Releves\\tnuot.pdf dans le dossier de l'application, puis Données > Actualiser tout. "
               "Ajouter dans Paramètres toute opération affichée « À traduire ».",
    }
    for ref, t in textes.items():
        ancien = fe.cellule(ref)
        s = re.search(r' s="(\d+)"', ancien).group(1)
        fe.poser(ref, c_texte(ref, ch, t, s))
    section = [
        ("A48", "6. Lot 0 – Passage à Excel (26/09/2026)", 55),
        ("B49", "Ancien logiciel", "Écritures, plan comptable, journaux, axes 1 et 2 et préfixes ne sont plus rechargés depuis ses exports : "
                "les tables sont dissociées de leurs requêtes. Excel est désormais la seule référence ; « Actualiser tout » ne met plus à jour que le relevé Banque 1."),
        ("B50", "Chemins relatifs", "Requête1 lit le relevé dans Releves\\tnuot.pdf, sous le dossier de l'application (Paramètres, E13:E16)."),
        ("B51", "Exercices", "Exercice court du 25/10/2025 au 31/12/2025, verrouillé (contrôle RG-04) ; exercice 2026 ouvert du 01/01 au 31/12/2026."),
        ("B52", "Isracard", "Mvt 412 à 416 : 580000 contre 512000 ; nouveaux Mvt 417 à 421 en OD : 600000 contre 580000. Résultat et trésorerie inchangés."),
        ("B53", "Référentiels", "13 codes Anal2 sans libellé et jamais utilisés supprimés ; SOC.005 à SOC.007, utilisés, attendent leur libellé. "
                "Solde du plan comptable et « Code suivant » des préfixes calculés."),
        ("B54", "Comptes de liaison", "Contrôles!M20:P23 suit 580000 (virements internes) et 470000 (attente) : 580000 porte un solde débiteur de "
                f"{soldes_fmt(COMPTE_VIREMENT)} à analyser au Lot 3 (virements passés d'un seul côté, B2 sans écriture)."),
        ("B55", "Traçabilité", "Chaque modification est inscrite dans l'onglet Journal des modifications."),
    ]
    for item in section:
        if isinstance(item[2], int):
            fe.poser(item[0], c_texte(item[0], ch, item[1], item[2]))
            fe.lignes[int(item[0][1:])][0] = ' ht="15.75" x14ac:dyDescent="0.2"'
        else:
            ref, lib, t = item
            r = ref[1:]
            fe.poser(f"B{r}", c_texte(f"B{r}", ch, lib, 59))
            fe.poser(f"C{r}", c_texte(f"C{r}", ch, t, 54))
    fe.remplacer('<dimension ref="A1:D46"/>', '<dimension ref="A1:D55"/>')
    fe.enregistrer()


SOLDES = {}


def soldes_fmt(compte):
    return f"{SOLDES.get(compte, 0):,.2f}".replace(",", " ").replace(".", ",")


def finaliser(p, noms_ajoutes, nom_journal):
    wb = p.lire("xl/workbook.xml")
    wb = wb.replace('<calcPr calcId="191029"/>', '<calcPr calcId="191029" fullCalcOnLoad="1"/>')
    p.ecrire("xl/workbook.xml", wb)
    # calcChain reconstruit par Excel
    rels = p.lire("xl/_rels/workbook.xml.rels")
    rels = re.sub(r'<Relationship Id="rId\d+" Type="[^"]*/calcChain" Target="calcChain.xml"/>', "", rels)
    p.ecrire("xl/_rels/workbook.xml.rels", rels)
    retirer_override(p, "xl/calcChain.xml")
    p.supprimer("xl/calcChain.xml")
    # docProps/app.xml : liste des feuilles et des noms
    app = p.lire("docProps/app.xml")
    feuilles_ = re.findall(r'<sheet name="([^"]+)"', wb)
    noms = [n for n in re.findall(r'<definedName name="([^"]+)"(?![^>]*hidden="1")([^>]*)>', wb)]
    titres = [x(n) for n in feuilles_]
    for n, attrs in noms:
        m = re.search(r'localSheetId="(\d+)"', attrs)
        titres.append(x(f"'{feuilles_[int(m.group(1))]}'!{n}" if m else n))
    app = re.sub(r"(<vt:lpstr>Feuilles de calcul</vt:lpstr></vt:variant><vt:variant><vt:i4>)\d+", rf"\g<1>{len(feuilles_)}", app)
    app = re.sub(r"(<vt:lpstr>Plages nommées</vt:lpstr></vt:variant><vt:variant><vt:i4>)\d+", rf"\g<1>{len(noms)}", app)
    app = re.sub(r'<TitlesOfParts><vt:vector size="\d+" baseType="lpstr">.*?</vt:vector></TitlesOfParts>',
                 f'<TitlesOfParts><vt:vector size="{len(titres)}" baseType="lpstr">' + "".join(f"<vt:lpstr>{t}</vt:lpstr>" for t in titres)
                 + "</vt:vector></TitlesOfParts>", app, flags=re.S)
    p.ecrire("docProps/app.xml", app)


# ---------------------------------------------------------------- lecture des valeurs

def lire_valeurs(chemin):
    wb = openpyxl.load_workbook(chemin, data_only=True)
    ws = wb["Écritures"]
    entetes = [c.value for c in ws[1]][:18]
    ecr = [list(r[:18]) for r in ws.iter_rows(min_row=2, values_only=True) if r[0] is not None]
    plan = {str(r[0]): (r[1], r[2]) for r in wb["Plan comptable"].iter_rows(min_row=2, max_col=3, values_only=True) if r[0]}
    axe1 = {r[0]: r[1] for r in wb["Axe 1 - Anal1"].iter_rows(min_row=2, max_col=3, values_only=True) if r[0]}
    axe2_lignes = [r for r in wb["Axe 2 - Anal2"].iter_rows(min_row=2, max_row=35, max_col=3, values_only=True) if r[0]]
    axe2 = {r[0]: (r[1] or "", r[2]) for r in axe2_lignes}
    return {"entetes": entetes, "ecritures": ecr, "plan": plan, "axe1": axe1, "axe2": axe2, "axe2_lignes": axe2_lignes}


def main(entree, sortie):
    valeurs = lire_valeurs(entree)
    p = Paquet(entree)
    ch = Chaines(p)
    f = feuilles(p)
    journal = []

    dissocier(p, journal)
    fe_param, noms = parametres(p, ch, f, journal)
    dernier_mvt, derniere_ligne = isracard(p, ch, f, valeurs, journal)
    fe_param.poser("E8", c_nombre("E8", dernier_mvt, S_SAISIE_ENTIER))
    fe_param.enregistrer()
    ajouter_noms(p, noms)

    # écritures après reclassement, pour les caches et soldes
    idx = {h: i for i, h in enumerate(valeurs["entetes"])}
    finales = []
    for l in valeurs["ecritures"]:
        compte = str(l[idx["Compte"]])
        if l[idx["Mvt"]] in range(412, 417) and compte == COMPTE_CHARGE:
            finales.append((COMPTE_VIREMENT, l[idx["Anal2"]], l[idx["Mvt"]], l[idx["Débit"]] or 0, l[idx["Crédit"]] or 0))
            finales.append((COMPTE_CHARGE, l[idx["Anal2"]], None, l[idx["Débit"]] or 0, 0))
            finales.append((COMPTE_VIREMENT, l[idx["Anal2"]], None, 0, l[idx["Débit"]] or 0))
        else:
            finales.append((compte, l[idx["Anal2"]], l[idx["Mvt"]], l[idx["Débit"]] or 0, l[idx["Crédit"]] or 0))
    soldes = {}
    for compte, _, _, d, c in finales:
        soldes[compte] = soldes.get(compte, 0) + d - c
    SOLDES.update({k: round(v, 2) for k, v in soldes.items()})

    referentiels(p, ch, f, valeurs, finales, journal)
    controles(p, ch, f, SOLDES, journal)
    journal.append(("Ajout", "onglet Journal des modifications", "", "table T_Journal"))
    nom_journal = onglet_journal(p, ch, journal)
    accueil_et_compte_rendu(p, ch, f, nom_journal, dernier_mvt)
    ch.enregistrer()
    finaliser(p, noms, nom_journal)
    p.enregistrer(sortie)
    print(f"{sortie} : {len(journal)} modifications journalisées, dernier Mvt {dernier_mvt}, dernière ligne {derniere_ligne}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
