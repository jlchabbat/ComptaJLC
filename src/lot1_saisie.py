"""Lot 1 — saisie guidée, création de codes, statut des codes Anal2.

    python src/lot1_saisie.py ComptaBB_lot0.xlsm ComptaBB.xlsm

S'applique au classeur produit par le Lot 0. Même méthode : édition directe
du XML, 100 % formules (décision Q5), rien n'est écrit dans les écritures.

Trois onglets :
- **Modèles** : T_ModelesOperation (types d'opération), T_Schemas (lignes
  générées par schéma), T_Paiements (moyens de paiement), T_TypesTiers.
- **Saisie** : cases jaunes, contrôles bloquants, aperçu, puis « lignes à
  reporter » à coller en valeurs sous T_Ecritures.
- **Codes** : nouveau code analytique (proposé d'après le préfixe), nouveau
  membre (compte 411), changement de statut d'un code Anal2 ; chaque action
  prépare aussi sa ligne pour le Journal des modifications.

Les schémas reprennent les conventions des écritures existantes : une
opération avec tiers = un Mvt de 4 lignes dans le journal du paiement
(facture puis règlement), 2 lignes sans règlement (journal VT ou HA) ; un
virement interne ou un paiement Isracard = deux Mvt passant par 580000.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lot0_preparation import (  # noqa: E402
    AUJOURDHUI, Chaines, Feuille, Paquet, ajouter_override, c_nombre, c_texte, col_num, feuilles, serial, tables, x,
)

AUTEUR = "Claude Code (Lot 1)"
S_DATE, S_MONTANT, S_TEXTE = 1, 2, 3
S_TITRE, S_SECTION, S_SOUS_SECTION, S_ENTETE, S_NOTE, S_LIEN, S_GRAS = 4, 8, 70, 9, 24, 41, 13
S_SAISIE, S_SAISIE_DATE, S_SAISIE_MONTANT = 18, 25, 43
DXF_OK, DXF_ERREUR = 24, 23

# ---------------------------------------------------------------- paramètres de la saisie

MODELES = [
    # Type, Schéma, Compte, Journal par défaut, Tiers, Paiement, Classe, Libellé type, Aide
    ("Cotisation membre", "RT", "700000", "VT", "Membre", "Facultatif", "7", "COTISATION",
     "Facture la cotisation au membre ; avec un moyen de paiement, le règlement est passé dans la même opération."),
    ("Facture manifestation (membre)", "RT", "710000", "VT", "Membre", "Facultatif", "7", "FACTURE MANIFESTATION",
     "Participation d'un membre à une manifestation, réglée ou non."),
    ("Recette d'opération (membre)", "RT", "720000", "VT", "Membre", "Facultatif", "7", "FACTURE OPERATION",
     "Recette d'une opération facturée à un membre."),
    ("Don reçu d'un membre", "RT", "725000", "VT", "Membre", "Facultatif", "7", "DON",
     "Don d'un membre, suivi sur son compte."),
    ("Règlement d'un membre", "RM", "", "", "Membre", "Obligatoire", "", "REGLEMENT",
     "Encaissement d'une facture déjà passée au membre."),
    ("Don reçu (sans tiers)", "RS", "725000", "", "Aucun", "Obligatoire", "7", "DON",
     "Don encaissé directement, sans compte de membre."),
    ("Subvention", "RS", "740000", "", "Aucun", "Obligatoire", "7", "SUBVENTION", "Subvention encaissée."),
    ("Intérêts perçus", "RS", "750000", "", "Aucun", "Obligatoire", "7", "INTERETS", "Intérêts versés par la banque."),
    ("Dépense directe", "DS", "", "", "Aucun", "Obligatoire", "6", "DEPENSE",
     "Dépense payée immédiatement : choisir le compte de charge dans « Compte »."),
    ("Frais bancaires", "DS", "600100", "", "Aucun", "Obligatoire", "6", "FRAIS BANCAIRES", "Frais prélevés par la banque."),
    ("Facture fournisseur", "DT", "", "HA", "Fournisseur", "Facultatif", "6", "FACTURE FOURNISSEUR",
     "Facture d'un fournisseur, réglée ou non : choisir le compte de charge dans « Compte »."),
    ("Règlement fournisseur", "RF", "", "", "Fournisseur", "Obligatoire", "", "REGLEMENT FOURNISSEUR",
     "Paiement d'une facture fournisseur déjà passée."),
    ("Virement interne", "VI", "", "", "Aucun", "Obligatoire", "", "VIREMENT INTERNE",
     "Virement entre deux comptes de l'association : choisir le compte qui reçoit dans « Vers »."),
    ("Paiement carte Isracard", "CB", "600000", "OD", "Aucun", "Obligatoire", "6", "CARTE ISRACARD",
     "Charge contre 580000, puis prélèvement 580000 contre la banque (décision Q2)."),
]

# Schéma, Ligne, Mvt, Rôle, Sens, Si réglé, Journal
SCHEMAS = [
    ("RT", 1, 1, "TIERS", "D", "Non", "PAIEMENT_OU_DEFAUT"),
    ("RT", 2, 1, "CONTREPARTIE", "C", "Non", "PAIEMENT_OU_DEFAUT"),
    ("RT", 3, 1, "TRESO", "D", "Oui", "PAIEMENT_OU_DEFAUT"),
    ("RT", 4, 1, "TIERS", "C", "Oui", "PAIEMENT_OU_DEFAUT"),
    ("DT", 1, 1, "CONTREPARTIE", "D", "Non", "PAIEMENT_OU_DEFAUT"),
    ("DT", 2, 1, "TIERS", "C", "Non", "PAIEMENT_OU_DEFAUT"),
    ("DT", 3, 1, "TIERS", "D", "Oui", "PAIEMENT_OU_DEFAUT"),
    ("DT", 4, 1, "TRESO", "C", "Oui", "PAIEMENT_OU_DEFAUT"),
    ("RS", 1, 1, "TRESO", "D", "Non", "PAIEMENT"),
    ("RS", 2, 1, "CONTREPARTIE", "C", "Non", "PAIEMENT"),
    ("DS", 1, 1, "CONTREPARTIE", "D", "Non", "PAIEMENT"),
    ("DS", 2, 1, "TRESO", "C", "Non", "PAIEMENT"),
    ("RM", 1, 1, "TRESO", "D", "Non", "PAIEMENT"),
    ("RM", 2, 1, "TIERS", "C", "Non", "PAIEMENT"),
    ("RF", 1, 1, "TIERS", "D", "Non", "PAIEMENT"),
    ("RF", 2, 1, "TRESO", "C", "Non", "PAIEMENT"),
    ("VI", 1, 1, "VIREMENT", "D", "Non", "PAIEMENT"),
    ("VI", 2, 1, "TRESO", "C", "Non", "PAIEMENT"),
    ("VI", 3, 2, "DEST", "D", "Non", "DESTINATION"),
    ("VI", 4, 2, "VIREMENT", "C", "Non", "DESTINATION"),
    ("CB", 1, 1, "CONTREPARTIE", "D", "Non", "DEFAUT"),
    ("CB", 2, 1, "VIREMENT", "C", "Non", "DEFAUT"),
    ("CB", 3, 2, "VIREMENT", "D", "Non", "PAIEMENT"),
    ("CB", 4, 2, "TRESO", "C", "Non", "PAIEMENT"),
]

PAIEMENTS = [
    ("Mizrahi compte courant", "B1", "512000"),
    ("Mizrahi épargne", "B2", "512100"),
    ("BIT", "B3", "512200"),
    ("Caisse (espèces)", "CA", "530000"),
    ("Non réglé", "", ""),
]

TYPES_TIERS = [("Membre", "411"), ("Fournisseur", "401")]

NB_LIGNES = 4          # lignes générées au plus par une opération (T_Schemas)
L_APERCU = 31          # première ligne de l'aperçu (Saisie)
L_ZONE = 42            # première ligne de la zone à reporter (Saisie)


# ---------------------------------------------------------------- outils

def lettre(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def c_f(ref, formule, s=None, texte=True, dynamique=False):
    """Cellule formule sans valeur en cache : Excel recalcule tout à l'ouverture."""
    st = f' s="{s}"' if s is not None else ""
    t = ' t="str"' if texte else ""
    if dynamique:
        return f'<c r="{ref}"{st}{t} cm="1"><f t="array" ref="{ref}">{x(formule)}</f></c>'
    return f'<c r="{ref}"{st}{t}><f>{x(formule)}</f></c>'


def c_val(ref, ch, valeur, s=None):
    if valeur in (None, ""):
        return f'<c r="{ref}" s="{s}"/>' if s is not None else None
    if isinstance(valeur, (int, float)):
        return c_nombre(ref, valeur, s)
    return c_texte(ref, ch, valeur, s)


def validation(sqref, formule1, invite="", titre="", erreur="", type_="list", operateur=None, formule2=None, bloquant=True):
    attrs = [f'type="{type_}"']
    if operateur:
        attrs.append(f'operator="{operateur}"')
    if not bloquant:
        attrs.append('errorStyle="warning"')
    attrs += ['allowBlank="1"', 'showInputMessage="1"', 'showErrorMessage="1"']
    if erreur:
        attrs += [f'errorTitle="{x(titre or "Valeur non valide")}"', f'error="{x(erreur)}"']
    if invite:
        attrs += [f'promptTitle="{x(titre)}"', f'prompt="{x(invite)}"']
    f2 = f"<formula2>{x(formule2)}</formula2>" if formule2 is not None else ""
    f1 = f"<formula1>{x(formule1)}</formula1>" if formule1 is not None else ""
    return f'<dataValidation {" ".join(attrs)} sqref="{sqref}">{f1}{f2}</dataValidation>'


class Classeur:
    def __init__(self, entree):
        self.p = Paquet(entree)
        self.ch = Chaines(self.p)
        self.noms = {}
        self.journal = []

    # ------------------------------------------------ onglets et tables
    def nouvel_onglet(self, nom, apres, cols, vue="", cf="", dv="", liens="", n_tables=0):
        p = self.p
        wb = p.lire("xl/workbook.xml")
        rels = p.lire("xl/_rels/workbook.xml.rels")
        n = max(int(v) for v in re.findall(r"worksheets/sheet(\d+)\.xml", rels)) + 1
        rid = "rId" + str(max(int(v) for v in re.findall(r'Id="rId(\d+)"', rels)) + 1)
        sheet_id = max(int(v) for v in re.findall(r'sheetId="(\d+)"', wb)) + 1
        noms_feuilles = re.findall(r'<sheet name="([^"]+)"', wb)
        pos = noms_feuilles.index(apres) + 1
        # décalage des noms locaux des onglets qui suivent
        wb = re.sub(r'localSheetId="(\d+)"', lambda m: f'localSheetId="{int(m.group(1)) + (1 if int(m.group(1)) >= pos else 0)}"', wb)
        m = re.search(rf'<sheet name="{re.escape(apres)}" [^>]*/>', wb)
        wb = wb[: m.end()] + f'<sheet name="{x(nom)}" sheetId="{sheet_id}" r:id="{rid}"/>' + wb[m.end():]
        wb = re.sub(r'activeTab="\d+"', 'activeTab="0"', wb)
        p.ecrire("xl/workbook.xml", wb)
        p.ecrire("xl/_rels/workbook.xml.rels", rels.replace("</Relationships>",
                 f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{n}.xml"/></Relationships>'))
        part = f"xl/worksheets/sheet{n}.xml"
        cache = ' hidden="1"'
        largeurs = "".join(f'<col min="{a}" max="{b}" width="{w}" customWidth="1"{cache if h else ""}/>' for a, b, w, h in cols)
        parts_tables = "".join(f'<tablePart r:id="rId{i + 1}"/>' for i in range(n_tables))
        xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
               'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="x14ac" '
               'xmlns:x14ac="http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac">'
               '<dimension ref="A1"/><sheetViews><sheetView showGridLines="0" workbookViewId="0">'
               f'{vue}</sheetView></sheetViews>'
               '<sheetFormatPr baseColWidth="10" defaultRowHeight="12" x14ac:dyDescent="0.2"/>'
               f'<cols>{largeurs}</cols><sheetData></sheetData>{cf}'
               + (f'<dataValidations count="{dv.count("<dataValidation ")}">{dv}</dataValidations>' if dv else "")
               + (f"<hyperlinks>{liens}</hyperlinks>" if liens else "")
               + '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>'
               + (f'<tableParts count="{n_tables}">{parts_tables}</tableParts>' if n_tables else "")
               + "</worksheet>")
        p.ecrire(part, xml)
        ajouter_override(p, part, "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
        return part

    def nouvelle_table(self, part_feuille, rid, nom, coin, entetes, lignes, calculees=None, styles=None):
        """Table à l'endroit `coin` ; calculees = {colonne: formule de colonne calculée}."""
        p, ch = self.p, self.ch
        calculees = calculees or {}
        styles = styles or {}
        fe = Feuille(p, part_feuille)
        c0, r0 = re.fullmatch(r"([A-Z]+)(\d+)", coin).groups()
        c0, r0 = col_num(c0), int(r0)
        for j, h in enumerate(entetes):
            fe.poser(f"{lettre(c0 + j)}{r0}", c_texte(f"{lettre(c0 + j)}{r0}", ch, h))
        for i, ligne in enumerate(lignes):
            r = r0 + 1 + i
            for j, h in enumerate(entetes):
                ref = f"{lettre(c0 + j)}{r}"
                if h in calculees:
                    fe.poser(ref, c_f(ref, calculees[h], styles.get(h)))
                else:
                    cel = c_val(ref, ch, ligne[j], styles.get(h))
                    if cel:
                        fe.poser(ref, cel)
        fe.enregistrer()
        fin = f"{lettre(c0 + len(entetes) - 1)}{r0 + len(lignes)}"
        ref = f"{lettre(c0)}{r0}:{fin}"
        n_table = max(int(v) for v in re.findall(r"xl/tables/table(\d+)\.xml", " ".join(p.ordre))) + 1
        table_id = max(int(re.search(r' id="(\d+)"', p.lire(t)).group(1)) for t in tables(p).values()) + 1
        cols = "".join(
            f'<tableColumn id="{j + 1}" name="{x(h)}"'
            + (f"><calculatedColumnFormula>{x(calculees[h])}</calculatedColumnFormula></tableColumn>" if h in calculees else "/>")
            for j, h in enumerate(entetes))
        part = f"xl/tables/table{n_table}.xml"
        p.ecrire(part, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                 f'<table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" id="{table_id}" name="{nom}" '
                 f'displayName="{nom}" ref="{ref}" totalsRowShown="0"><autoFilter ref="{ref}"/>'
                 f'<tableColumns count="{len(entetes)}">{cols}</tableColumns>'
                 '<tableStyleInfo name="TableStyleLight9" showFirstColumn="0" showLastColumn="0" showRowStripes="1" showColumnStripes="0"/></table>')
        ajouter_override(p, part, "application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml")
        rels = part_feuille.replace("worksheets/", "worksheets/_rels/") + ".rels"
        rel = f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table{n_table}.xml"/>'
        if rels in p.brut or rels in p.texte:
            p.ecrire(rels, p.lire(rels).replace("</Relationships>", rel + "</Relationships>"))
        else:
            p.ecrire(rels, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                     f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rel}</Relationships>')
        return ref

    def nommer(self, nom, ref):
        self.noms[nom] = ref

    def enregistrer_noms(self):
        wb = self.p.lire("xl/workbook.xml")
        m = re.search(r"<definedNames>(.*?)</definedNames>", wb, re.S)
        existants = re.findall(r"<definedName .*?</definedName>", m.group(1), re.S)
        existants += [f'<definedName name="{n}">{x(r)}</definedName>' for n, r in self.noms.items()]
        cle = lambda e: (re.search(r'name="([^"]+)"', e).group(1).lower(), re.search(r'localSheetId="(\d+)"', e) is None)
        self.p.ecrire("xl/workbook.xml", wb.replace(m.group(0), "<definedNames>" + "".join(sorted(existants, key=cle)) + "</definedNames>"))

    def dimension(self, part):
        s = self.p.lire(part)
        refs = re.findall(r'<c r="([A-Z]+)(\d+)"', s)
        derniere = max(int(r) for _, r in refs)
        col = lettre(max(col_num(c) for c, _ in refs))
        self.p.ecrire(part, re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:{col}{derniere}"/>', s, count=1))


# ---------------------------------------------------------------- onglet Modèles

def onglet_modeles(cl):
    ch = cl.ch
    part = cl.nouvel_onglet("Modèles", "Paramètres", [(1, 1, 30, 0), (2, 2, 8, 0), (3, 3, 9, 0), (4, 4, 9, 0), (5, 5, 11, 0),
                                                      (6, 6, 11, 0), (7, 7, 7, 0), (8, 8, 22, 0), (9, 9, 70, 0), (10, 10, 3, 0),
                                                      (11, 11, 22, 0), (12, 12, 8, 0), (13, 13, 9, 0), (14, 14, 3, 0),
                                                      (15, 21, 12, 0), (22, 22, 22, 0)],
                            liens='<hyperlink ref="K1" location="\'Accueil\'!A1" tooltip="Retour au menu" display="← Accueil"/>',
                            n_tables=4)
    fe = Feuille(cl.p, part)
    fe.poser("A1", c_texte("A1", ch, "Modèles d'opérations et moyens de paiement", S_TITRE))
    fe.poser("K1", c_texte("K1", ch, "← Accueil", S_LIEN))
    fe.poser("A2", c_texte("A2", ch, "Paramètres de l'onglet Saisie. Un type d'opération = une ligne de T_ModelesOperation ; "
                                     "les lignes d'écriture générées sont décrites par son schéma dans T_Schemas. Ajouter ou modifier "
                                     "une ligne suffit : aucune formule n'est à retoucher.", S_NOTE))
    fe.enregistrer()
    cl.nouvelle_table(part, "rId1", "T_ModelesOperation", "A4",
                      ["Type", "Schéma", "Compte", "Journal par défaut", "Tiers", "Paiement", "Classe", "Libellé type", "Aide"],
                      MODELES)
    cl.nouvelle_table(part, "rId2", "T_Paiements", "K4", ["Moyen", "Journal", "Compte"], PAIEMENTS)
    cl.nouvelle_table(part, "rId3", "T_TypesTiers", "K12", ["Tiers", "Préfixe compte"], TYPES_TIERS)
    cl.nouvelle_table(part, "rId4", "T_Schemas", "O4", ["Schéma", "Ligne", "Mvt", "Rôle", "Sens", "Si réglé", "Journal", "Clé"],
                      [s + ("",) for s in SCHEMAS],
                      calculees={"Clé": 'T_Schemas[[#This Row],[Schéma]]&"|"&T_Schemas[[#This Row],[Ligne]]'})
    fe = Feuille(cl.p, part)
    notes = [
        ("K17", "Schémas : RT recette avec tiers · DT dépense avec tiers · RS recette sans tiers · DS dépense sans tiers ·"),
        ("K18", "RM / RF règlement membre / fournisseur · VI virement interne · CB paiement carte Isracard."),
        ("K19", "Rôles : TIERS compte du tiers · CONTREPARTIE compte du modèle (ou saisi) · TRESO banque ou caisse du paiement ·"),
        ("K20", "DEST banque qui reçoit un virement · VIREMENT compte de virement interne (P_CompteVirement)."),
        ("K21", "Journal : PAIEMENT_OU_DEFAUT = journal du paiement si l'opération est réglée, sinon journal par défaut du modèle."),
        ("K22", "« Si réglé » = Oui : la ligne n'existe que si un moyen de paiement est choisi."),
    ]
    for ref, t in notes:
        fe.poser(ref, c_texte(ref, ch, t, S_NOTE))
    fe.enregistrer()
    cl.dimension(part)
    cl.nommer("L_Types", "T_ModelesOperation[Type]")
    cl.nommer("L_Paiements", "T_Paiements[Moyen]")
    cl.nommer("L_Prefixes", "T_Prefixes[Préfixe]")
    cl.journal.append(("Ajout", "onglet Modèles", "", f"T_ModelesOperation ({len(MODELES)} types), T_Schemas, T_Paiements, T_TypesTiers"))


# ---------------------------------------------------------------- onglet Saisie

ENTREES = [
    # ligne, libellé, style, validation, aide
    (4, "Date", S_SAISIE_DATE, "date", "jj/mm/aaaa, dans l'exercice ouvert"),
    (5, "Type d'opération", S_SAISIE, "types", ""),
    (6, "Tiers (membre ou fournisseur)", S_SAISIE, "tiers", ""),
    (7, "Montant (₪)", S_SAISIE_MONTANT, "montant", "toujours positif"),
    (8, "Moyen de paiement", S_SAISIE, "paiements", ""),
    (9, "Vers (virement interne)", S_SAISIE, "paiements2", ""),
    (10, "Événement / projet (Anal2)", S_SAISIE, "anal2", ""),
    (11, "Compte (si différent du modèle)", S_SAISIE, "comptes", ""),
    (12, "Remboursement (opération inverse)", S_SAISIE, "ouinon", ""),
    (13, "Libellé (facultatif)", S_SAISIE, "libelle", ""),
]

# Cellules de calcul (colonne R, libellé en Q) : nom, formule
CALCULS = [
    ("SA_Mod", 'IFERROR(MATCH($C$5,T_ModelesOperation[Type],0),0)'),
    ("SA_Schema", 'IF(SA_Mod=0,"",INDEX(T_ModelesOperation[Schéma],SA_Mod)&"")'),
    ("SA_TiersType", 'IF(SA_Mod=0,"",INDEX(T_ModelesOperation[Tiers],SA_Mod)&"")'),
    ("SA_PrefTiers", 'IFERROR(INDEX(T_TypesTiers[Préfixe compte],MATCH(SA_TiersType,T_TypesTiers[Tiers],0))&"","")'),
    ("SA_Paiement", 'IF(SA_Mod=0,"",INDEX(T_ModelesOperation[Paiement],SA_Mod)&"")'),
    ("SA_Classe", 'IF(SA_Mod=0,"",INDEX(T_ModelesOperation[Classe],SA_Mod)&"")'),
    ("SA_PaiIdx", 'IFERROR(MATCH($C$8,T_Paiements[Moyen],0),0)'),
    ("SA_JnlPai", 'IF(SA_PaiIdx=0,"",INDEX(T_Paiements[Journal],SA_PaiIdx)&"")'),
    ("SA_CptPai", 'IF(SA_PaiIdx=0,"",INDEX(T_Paiements[Compte],SA_PaiIdx)&"")'),
    ("SA_Regle", 'SA_JnlPai<>""'),
    ("SA_DestIdx", 'IFERROR(MATCH($C$9,T_Paiements[Moyen],0),0)'),
    ("SA_JnlDest", 'IF(SA_DestIdx=0,"",INDEX(T_Paiements[Journal],SA_DestIdx)&"")'),
    ("SA_CptDest", 'IF(SA_DestIdx=0,"",INDEX(T_Paiements[Compte],SA_DestIdx)&"")'),
    ("SA_JnlDef", 'IF(SA_Mod=0,"",INDEX(T_ModelesOperation[Journal par défaut],SA_Mod)&"")'),
    ("SA_CptModele", 'IF(SA_Mod=0,"",INDEX(T_ModelesOperation[Compte],SA_Mod)&"")'),
    ("SA_CptContre", 'IF(TRIM($C$11)<>"",TRIM($C$11)&"",SA_CptModele)'),
    ("SA_CptTiers", 'IFERROR(MID($C$6,FIND("(",$C$6)+1,FIND(")",$C$6)-FIND("(",$C$6)-1),"")'),
    ("SA_NomTiers", 'IFERROR(TRIM(LEFT($C$6,FIND("(",$C$6)-1)),TRIM($C$6))'),
    ("SA_Inverse", '$C$12="Oui"'),
    ("SA_Montant", 'IF(ISNUMBER($C$7),ROUND($C$7,2),0)'),
    ("SA_Mvt", 'MAX(T_Ecritures[Mvt])+1'),
    ("SA_Piece", 'MAX(T_Ecritures[Pièce])+1'),
    ("SA_NbLignes", 'IF(SA_Schema="",0,COUNTIFS(T_Schemas[Schéma],SA_Schema,T_Schemas[Si réglé],"Non")'
                    '+IF(SA_Regle,COUNTIFS(T_Schemas[Schéma],SA_Schema,T_Schemas[Si réglé],"Oui"),0))'),
    ("SA_Libelle", 'IF(TRIM($C$13)<>"",UPPER(TRIM($C$13)),IF(SA_Mod=0,"",IF(SA_Inverse,"REMBOURSEMENT ","")'
                   '&INDEX(T_ModelesOperation[Libellé type],SA_Mod)&IF(SA_NomTiers<>""," - "&UPPER(SA_NomTiers),"")))'),
    ("SA_Contre", 'IF(SA_Schema="",FALSE,COUNTIFS(T_Schemas[Schéma],SA_Schema,T_Schemas[Rôle],"CONTREPARTIE")>0)'),
    ("SA_NbErreurs", 'COUNTIF($C$18:$C$28,"Erreur")'),
    ("SA_OK", 'AND(SA_NbLignes>0,SA_NbErreurs=0)'),
]

def jma(date):
    """Date en texte jj/mm/aaaa sans code de format dépendant de la langue d'Excel."""
    return f'TEXT(DAY({date}),"00")&"/"&TEXT(MONTH({date}),"00")&"/"&YEAR({date})'


CONTROLES = [
    (18, "Date", 'IF(NOT(ISNUMBER($C$4)),"Saisir la date.",IF($C$4<=P_DateCloture,"Date dans la période close (jusqu\'au "'
                 f'&{jma("P_DateCloture")}&").",IF(OR($C$4<P_DebutExercice,$C$4>P_FinExercice),'
                 f'"Date hors de l\'exercice ouvert ("&{jma("P_DebutExercice")}&" au "&{jma("P_FinExercice")}&").","")))'),
    (19, "Type d'opération", 'IF(SA_Mod=0,"Choisir un type d\'opération dans la liste.","")'),
    (20, "Montant", 'IF(SA_Montant<=0,"Saisir un montant positif ; pour une opération inverse, choisir Remboursement = Oui.","")'),
    (21, "Tiers", 'IF(SA_Mod=0,"",IF(SA_TiersType="Aucun",IF(TRIM($C$6)<>"","Ce type d\'opération n\'a pas de tiers : vider la case.",""),'
                  'IF(SA_CptTiers="","Choisir le "&LOWER(SA_TiersType)&" dans la liste.",IF(COUNTIF(L_Comptes,SA_CptTiers)=0,'
                  '"Compte du tiers absent du plan comptable : "&SA_CptTiers&".",IF(LEFT(SA_CptTiers,LEN(SA_PrefTiers))<>SA_PrefTiers,'
                  '"Ce type d\'opération attend un "&LOWER(SA_TiersType)&" (compte "&SA_PrefTiers&"…).","")))))'),
    (22, "Moyen de paiement", 'IF(AND($C$8<>"",SA_PaiIdx=0),"Moyen de paiement inconnu.",IF(AND(SA_Paiement="Obligatoire",NOT(SA_Regle)),'
                              '"Choisir la banque ou la caisse.",""))'),
    (23, "Virement : compte qui reçoit", 'IF(SA_Schema="VI",IF(SA_JnlDest="","Choisir le compte qui reçoit le virement.",'
                                         'IF(SA_JnlDest=SA_JnlPai,"Les deux comptes du virement doivent être différents.","")),'
                                         'IF(TRIM($C$9)<>"","Cette case ne sert qu\'aux virements internes : la vider.",""))'),
    (24, "Événement / projet", 'IF(TRIM($C$10)="","Choisir l\'événement ou le projet (Anal2).",IF(COUNTIF(L_Anal2,$C$10)=0,"Code Anal2 inconnu.",""))'),
    (25, "Compte", 'IF(NOT(SA_Contre),IF(TRIM($C$11)<>"","Ce type d\'opération n\'utilise pas de compte : vider la case.",""),'
                   'IF(SA_CptContre="","Choisir le compte (classe "&SA_Classe&") dans la case Compte.",IF(COUNTIF(L_Comptes,SA_CptContre)=0,'
                   '"Compte absent du plan comptable.",IF(AND(SA_Classe<>"",LEFT(SA_CptContre,1)<>SA_Classe),'
                   '"Ce type d\'opération attend un compte de classe "&SA_Classe&".",""))))'),
    (26, "Comptes et journaux générés", f'IF(SA_NbLignes=0,"",IF(SUMPRODUCT(($G${L_APERCU}:$G${L_APERCU + NB_LIGNES - 1}="Compte inconnu")*($F${L_APERCU}:$F${L_APERCU + NB_LIGNES - 1}<>""))>0,'
                                        f'"Un compte généré est absent du plan comptable.",IF(SUMPRODUCT(($C${L_APERCU}:$C${L_APERCU + NB_LIGNES - 1}<>"")'
                                        f'*(COUNTIF(L_Journaux,$C${L_APERCU}:$C${L_APERCU + NB_LIGNES - 1})=0))>0,"Un journal généré est inconnu.","")))'),
    (27, "Équilibre", f'IF(SA_NbLignes=0,"",IF(ROUND(SUM($I${L_APERCU}:$I${L_APERCU + NB_LIGNES - 1})-SUM($J${L_APERCU}:$J${L_APERCU + NB_LIGNES - 1}),2)<>0,'
                      '"Écritures déséquilibrées.",""))'),
    (28, "Déjà reportée ?", 'IF(OR(SA_Montant<=0,NOT(ISNUMBER($C$4)),SA_Libelle=""),"",IF(COUNTIFS(T_Ecritures[Date],$C$4,T_Ecritures[Libellé],'
                            'SA_Libelle,T_Ecritures[Débit],SA_Montant)>0,"Cette opération est déjà dans Écritures (même date, libellé et '
                            'montant) : vider les cases jaunes avant une nouvelle saisie.",""))'),
]


def onglet_saisie(cl):
    ch = cl.ch
    n_ap = NB_LIGNES
    dv = "".join([
        validation("C4", "P_DebutExercice", "Date de l'opération, dans l'exercice ouvert.", "Date",
                   "La date doit être dans l'exercice ouvert (onglet Paramètres).", type_="date", operateur="between", formule2="P_FinExercice"),
        validation("C5", "L_Types", "Choisir le type d'opération ; les écritures sont générées selon son modèle (onglet Modèles).",
                   "Type d'opération", "Choisir un type dans la liste."),
        validation("C6", "_xlfn.ANCHORARRAY($Y$4)", "Membre ou fournisseur, selon le type d'opération. Laisser vide s'il n'y en a pas.",
                   "Tiers", "Choisir un tiers dans la liste (ajouter d'abord un nouveau membre dans l'onglet Codes)."),
        validation("C7", "0", "Montant en shekels, toujours positif.", "Montant", "Saisir un nombre positif.",
                   type_="decimal", operateur="greaterThan"),
        validation("C8", "L_Paiements", "Banque ou caisse utilisée. « Non réglé » pour une facture qui sera payée plus tard.",
                   "Moyen de paiement", "Choisir dans la liste."),
        validation("C9", "L_Paiements", "Seulement pour un virement interne : le compte qui reçoit l'argent.", "Vers",
                   "Choisir dans la liste."),
        validation("C10", "L_Anal2", "Événement ou projet concerné (onglet Axe 2). Pour en créer un : onglet Codes.",
                   "Événement / projet", "Choisir un code dans la liste."),
        validation("C11", "L_Comptes", "À remplir seulement pour changer le compte proposé par le modèle, ou quand le modèle n'en a pas.",
                   "Compte", "Choisir un compte du plan comptable."),
        validation("C12", '"Oui,Non"', "Oui pour un remboursement : toutes les écritures sont inversées.", "Remboursement",
                   "Choisir Oui ou Non."),
        validation("C13", "60", "Laisser vide pour le libellé proposé en D13.", "Libellé", "60 caractères au plus.",
                   type_="textLength", operateur="lessThanOrEqual"),
    ])
    cf = (f'<conditionalFormatting sqref="C18:C28"><cfRule type="cellIs" dxfId="{DXF_OK}" priority="1" operator="equal"><formula>"OK"</formula></cfRule>'
          f'<cfRule type="cellIs" dxfId="{DXF_ERREUR}" priority="2" operator="equal"><formula>"Erreur"</formula></cfRule></conditionalFormatting>'
          f'<conditionalFormatting sqref="B16"><cfRule type="expression" dxfId="{DXF_OK}" priority="3"><formula>SA_OK</formula></cfRule>'
          f'<cfRule type="expression" dxfId="{DXF_ERREUR}" priority="4"><formula>AND(NOT(SA_OK),OR($C$4&lt;&gt;"",$C$5&lt;&gt;""))</formula></cfRule></conditionalFormatting>'
          f'<conditionalFormatting sqref="B{L_ZONE}:N{L_ZONE + n_ap - 1}"><cfRule type="expression" dxfId="{DXF_OK}" priority="5">'
          f'<formula>AND(SA_OK,ROW()-{L_ZONE - 1}&lt;=SA_NbLignes)</formula></cfRule></conditionalFormatting>')
    part = cl.nouvel_onglet("Saisie", "Accueil",
                            [(1, 1, 2, 0), (2, 2, 30, 0), (3, 3, 32, 0), (4, 4, 11, 0), (5, 5, 8, 0), (6, 6, 12, 0),
                             (7, 7, 22, 0), (8, 8, 40, 0), (9, 10, 11, 0), (11, 11, 7, 0), (12, 12, 8, 0), (13, 13, 9, 0),
                             (14, 14, 5, 0), (15, 16, 22, 0), (17, 23, 16, 1), (24, 25, 34, 1)],
                            vue='<selection activeCell="C4" sqref="C4"/>', cf=cf, dv=dv,
                            liens='<hyperlink ref="H1" location="\'Accueil\'!A1" tooltip="Retour au menu" display="← Accueil"/>')
    fe = Feuille(cl.p, part)
    fe.poser("B1", c_texte("B1", ch, "Saisie guidée d'une opération", S_TITRE))
    fe.poser("H1", c_texte("H1", ch, "← Accueil", S_LIEN))
    fe.poser("B2", c_texte("B2", ch, "Remplir les cases jaunes, vérifier que tous les contrôles sont OK, puis reporter les lignes vertes "
                                     "(partie 4) sous la table Écritures. Rien n'est écrit tant que vous ne collez pas.", S_NOTE))
    fe.poser("B3", c_texte("B3", ch, "1. L'opération", S_SECTION))
    for r, lib, s, _, aide in ENTREES:
        fe.poser(f"B{r}", c_texte(f"B{r}", ch, lib))
        fe.poser(f"C{r}", f'<c r="C{r}" s="{s}"/>')
        if aide:
            fe.poser(f"D{r}", c_texte(f"D{r}", ch, aide, S_NOTE))
    # informations calculées en D (en face des entrées)
    infos = {
        5: 'IF(SA_Mod=0,"",INDEX(T_ModelesOperation[Aide],SA_Mod))',
        6: 'IF(SA_TiersType="","",IF(SA_TiersType="Aucun","Pas de tiers pour ce type.",IF(SA_CptTiers="",'
           '"Choisir un "&LOWER(SA_TiersType)&" (compte "&SA_PrefTiers&"…).","Compte "&SA_CptTiers)))',
        8: 'IF(SA_Regle,"Journal "&SA_JnlPai&" · compte "&SA_CptPai,IF(SA_Paiement="Facultatif","Non réglé : facture seule (journal "&SA_JnlDef&")",""))',
        9: 'IF(SA_JnlDest="","","Journal "&SA_JnlDest&" · compte "&SA_CptDest)',
        10: 'IF(TRIM($C$10)="","",IFERROR(INDEX(T_Axe2[Libellé],MATCH($C$10,T_Axe2[Code],0)),"Code introuvable"))',
        11: 'IF(SA_CptContre="","",SA_CptContre&" – "&IFERROR(INDEX(T_PlanComptable[Libellé compte],MATCH(SA_CptContre,T_PlanComptable[Compte],0)),"compte inconnu")&IF(TRIM($C$11)="","  (compte du modèle)",""))',
        13: 'IF(SA_Libelle="","","Libellé retenu : "&SA_Libelle)',
    }
    for r, f_ in infos.items():
        fe.poser(f"D{r}", c_f(f"D{r}", f_, S_NOTE if r != 11 else S_TEXTE))
    fe.poser("E4", c_f("E4", 'IF(SA_Mod=0,"","Mvt "&SA_Mvt&" · pièce "&SA_Piece&" proposés")', S_NOTE))

    fe.poser("B15", c_texte("B15", ch, "2. Contrôles", S_SECTION))
    fe.poser("B16", c_f("B16", 'IF(AND($C$4="",$C$5=""),"Remplir les cases jaunes.",IF(SA_OK,"PRÊT À REPORTER : "&SA_NbLignes&" lignes, Mvt "&SA_Mvt'
                               f'&IF(MAX($U${L_APERCU}:$U${L_APERCU + n_ap - 1})>1," et "&(SA_Mvt+1),""),"À COMPLÉTER : "&SA_NbErreurs&" point(s) à corriger"))', S_GRAS))
    fe.poser("B17", c_texte("B17", ch, "Contrôle", S_ENTETE))
    fe.poser("C17", c_texte("C17", ch, "Résultat", S_ENTETE))
    fe.poser("D17", c_texte("D17", ch, "À faire", S_ENTETE))
    for r, lib, msg in CONTROLES:
        fe.poser(f"B{r}", c_texte(f"B{r}", ch, lib))
        fe.poser(f"D{r}", c_f(f"D{r}", msg))
        fe.poser(f"C{r}", c_f(f"C{r}", f'IF(AND($C$4="",$C$5=""),"",IF(IFERROR(D{r}="",FALSE),"OK","Erreur"))'))

    # calculs intermédiaires (colonnes Q:R masquées)
    fe.poser("Q3", c_texte("Q3", ch, "Calculs (ne pas modifier)", S_SOUS_SECTION))
    for i, (nom, f_) in enumerate(CALCULS):
        r = 4 + i
        fe.poser(f"Q{r}", c_texte(f"Q{r}", ch, nom))
        texte = nom not in ("SA_Mod", "SA_Regle", "SA_PaiIdx", "SA_DestIdx", "SA_Inverse", "SA_Montant", "SA_Mvt",
                            "SA_Piece", "SA_NbLignes", "SA_Contre", "SA_NbErreurs", "SA_OK")
        fe.poser(f"R{r}", c_f(f"R{r}", f_, texte=texte))
        cl.nommer(nom, f"Saisie!$R${r}")
    # liste des tiers (colonne Y masquée)
    fe.poser("Y3", c_texte("Y3", ch, "Tiers proposés (calculé)", S_SOUS_SECTION))
    fe.poser("Y4", c_f("Y4", '_xlfn._xlws.SORT(_xlfn._xlws.FILTER(T_PlanComptable[Libellé compte]&" ("&T_PlanComptable[Compte]&")",'
                             'IF(SA_PrefTiers="",ISNUMBER(MATCH(LEFT(T_PlanComptable[Compte],3),T_TypesTiers[Préfixe compte],0)),'
                             'LEFT(T_PlanComptable[Compte],LEN(SA_PrefTiers))=SA_PrefTiers),"(aucun)"))', dynamique=True))

    # 3. aperçu
    fe.poser(f"B{L_APERCU - 2}", c_texte(f"B{L_APERCU - 2}", ch, "3. Écritures générées", S_SECTION))
    entetes = ["Date", "Jnl", "Mvt", "Pièce", "Compte", "Intitulé", "Libellé", "Débit", "Crédit", "Solde", "Anal1", "Anal2", "Let",
               "Libellé Axe2", "Libellé Axe1"]
    for j, h in enumerate(entetes):
        ref = f"{lettre(2 + j)}{L_APERCU - 1}"
        fe.poser(ref, c_texte(ref, ch, h, S_ENTETE))
    for i in range(1, n_ap + 1):
        r = L_APERCU + i - 1
        g = f"$R{r}=0"
        aides = {
            "R": f'IF({i}>SA_NbLignes,0,IFERROR(MATCH(SA_Schema&"|{i}",T_Schemas[Clé],0),0))',
            "S": f'IF({g},"",INDEX(T_Schemas[Rôle],$R{r}))',
            "T": f'IF({g},"",INDEX(T_Schemas[Sens],$R{r}))',
            "U": f'IF({g},0,INDEX(T_Schemas[Mvt],$R{r}))',
            "V": f'IF({g},"",INDEX(T_Schemas[Journal],$R{r}))',
            "W": f'IF({g},"",IF(SA_Inverse,IF($T{r}="D","C","D"),$T{r}))',
        }
        for c, f_ in aides.items():
            fe.poser(f"{c}{r}", c_f(f"{c}{r}", f_, texte=c not in "RU"))
        cellules = {
            "B": (f'IF({g},"",$C$4)', S_DATE, False),
            "C": (f'IF({g},"",IF($V{r}="DEFAUT",SA_JnlDef,IF($V{r}="PAIEMENT",SA_JnlPai,IF($V{r}="DESTINATION",SA_JnlDest,'
                  f'IF(SA_Regle,SA_JnlPai,SA_JnlDef)))))', None, True),
            "D": (f'IF({g},"",SA_Mvt+$U{r}-1)', None, False),
            "E": (f'IF({g},"",SA_Piece+$U{r}-1)', None, False),
            "F": (f'IF({g},"",IF($S{r}="TIERS",SA_CptTiers,IF($S{r}="CONTREPARTIE",SA_CptContre,IF($S{r}="TRESO",SA_CptPai,'
                  f'IF($S{r}="DEST",SA_CptDest,IF($S{r}="VIREMENT",P_CompteVirement&"",""))))))', None, True),
            "G": (f'IF({g},"",IFERROR(INDEX(T_PlanComptable[Libellé compte],MATCH($F{r},T_PlanComptable[Compte],0)),"Compte inconnu"))', None, True),
            "H": (f'IF({g},"",SA_Libelle)', None, True),
            "I": (f'IF({g},"",IF($W{r}="D",SA_Montant,0))', S_MONTANT, False),
            "J": (f'IF({g},"",IF($W{r}="C",SA_Montant,0))', S_MONTANT, False),
            "K": (f'IF({g},"",0)', S_MONTANT, False),
            "L": (f'IF({g},"",IFERROR(INDEX(T_PlanComptable[Axe 1 (Anal1)],MATCH($F{r},T_PlanComptable[Compte],0)),""))', None, True),
            "M": (f'IF({g},"",$C$10)', None, True),
            "O": (f'IF({g},"",IFERROR(INDEX(T_Axe2[Libellé],MATCH($M{r},T_Axe2[Code],0)),"Code introuvable"))', None, True),
            "P": (f'IF({g},"",IF($L{r}="","",IFERROR(INDEX(T_Axe1[Libellé],MATCH($L{r},T_Axe1[Code],0)),"Code introuvable")))', None, True),
        }
        for c, (f_, s, texte) in cellules.items():
            fe.poser(f"{c}{r}", c_f(f"{c}{r}", f_, s, texte=texte))

    # 4. zone à reporter : mêmes colonnes que T_Ecritures (A:M), Intitulé, Anal1 et Let laissés vides
    fe.poser(f"B{L_ZONE - 3}", c_texte(f"B{L_ZONE - 3}", ch, "4. Lignes à reporter dans Écritures", S_SECTION))
    fe.poser(f"B{L_ZONE - 2}", c_f(f"B{L_ZONE - 2}",
             f'IF(SA_OK,"Sélectionner B{L_ZONE}:N"&({L_ZONE - 1}+SA_NbLignes)&", Copier ; dans Écritures, cliquer la cellule A"'
             '&(ROWS(T_Ecritures[Date])+2-(COUNT(T_Ecritures[Date])=0))&" (première ligne vide sous la table) ; Collage spécial › Valeurs, en cochant « Blancs non compris ».",'
             '"Rien à reporter tant que tous les contrôles ne sont pas OK.")', S_GRAS))
    fe.poser(f"H{L_ZONE - 3}", c_f(f"H{L_ZONE - 3}", 'HYPERLINK("#\'Écritures\'!A"&(ROWS(T_Ecritures[Date])+2-(COUNT(T_Ecritures[Date])=0)),"→ Aller à la première ligne vide d\'Écritures")', S_LIEN))
    for j, h in enumerate(entetes[:13]):
        ref = f"{lettre(2 + j)}{L_ZONE - 1}"
        fe.poser(ref, c_texte(ref, ch, {"Intitulé": "(Intitulé : calculé)", "Anal1": "(Anal1 : calculé)", "Let": "(Let : vide)"}.get(h, h), S_ENTETE))
    for i in range(n_ap):
        r, ra = L_ZONE + i, L_APERCU + i
        for c, s in (("B", S_DATE), ("C", None), ("D", None), ("E", None), ("F", None), ("H", None), ("I", S_MONTANT),
                     ("J", S_MONTANT), ("K", S_MONTANT), ("M", None)):
            texte = c in "CFHM"
            fe.poser(f"{c}{r}", c_f(f"{c}{r}", f'IF(AND(SA_OK,$R{ra}<>0),{c}{ra},"")', s, texte=texte))
    fe.poser(f"B{L_ZONE + n_ap + 1}", c_texte(f"B{L_ZONE + n_ap + 1}", ch,
             "Après le collage : les lignes apparaissent dans Écritures avec leur Intitulé et leur Anal1 calculés, et le contrôle "
             "« Déjà reportée ? » passe en Erreur ici. Vider alors les cases jaunes pour la saisie suivante.", S_NOTE))
    fe.enregistrer()
    cl.dimension(part)
    cl.journal.append(("Ajout", "onglet Saisie", "", "saisie guidée : 10 entrées, 11 contrôles bloquants, aperçu, lignes à reporter"))
    return part


# ---------------------------------------------------------------- onglet Codes

def onglet_codes(cl):
    ch = cl.ch
    dv = "".join([
        validation("C6", "L_Prefixes", "Préfixe du nouveau code ; le numéro est proposé automatiquement.", "Préfixe", "Choisir un préfixe."),
        validation("C8", '"0,1,2"', "0 = Non affecté, 1 = En cours, 2 = Terminé (axe 2).", "Statut", "Choisir 0, 1 ou 2."),
        validation("C29", "L_Anal2", "Code dont le statut change.", "Code Anal2", "Choisir un code dans la liste."),
        validation("C33", '"0,1,2"', "0 = Non affecté, 1 = En cours, 2 = Terminé.", "Nouveau statut", "Choisir 0, 1 ou 2."),
        validation("C34", '"Oui"', "Obligatoire si le code est déjà utilisé dans des écritures.", "Confirmation", "Choisir Oui."),
    ])
    cf = "".join(
        f'<conditionalFormatting sqref="{sq}"><cfRule type="cellIs" dxfId="{DXF_OK}" priority="{2 * k + 1}" operator="equal"><formula>"OK"</formula></cfRule>'
        f'<cfRule type="cellIs" dxfId="{DXF_ERREUR}" priority="{2 * k + 2}" operator="equal"><formula>"Erreur"</formula></cfRule></conditionalFormatting>'
        for k, sq in enumerate(("C11", "C24", "C37")))
    part = cl.nouvel_onglet("Codes", "Saisie", [(1, 1, 2, 0), (2, 2, 34, 0), (3, 3, 34, 0), (4, 4, 16, 0), (5, 5, 16, 0),
                                                 (6, 6, 16, 0), (7, 7, 30, 0), (8, 8, 30, 0), (9, 9, 12, 0), (18, 18, 12, 1)],
                            vue='<selection activeCell="C3" sqref="C3"/>', cf=cf, dv=dv,
                            liens='<hyperlink ref="H1" location="\'Accueil\'!A1" tooltip="Retour au menu" display="← Accueil"/>')
    fe = Feuille(cl.p, part)
    P = fe.poser

    def t(ref, texte, s=None):
        P(ref, c_texte(ref, ch, texte, s))

    def f(ref, formule, s=None, texte=True):
        P(ref, c_f(ref, formule, s, texte=texte))

    t("B1", "Créer un code, un membre, changer un statut", S_TITRE)
    t("H1", "← Accueil", S_LIEN)
    t("B2", "Chaque bloc prépare les lignes à coller (en valeurs) dans la table concernée et dans le Journal des modifications.", S_NOTE)
    t("B3", "Votre nom (auteur des modifications)")
    P("C3", '<c r="C3" s="18"/>')
    cl.nommer("CO_Auteur", "Codes!$C$3")
    journal_zone = 'HYPERLINK("#\'Journal des modifications\'!A"&(ROWS(T_Journal[Date])+5),"→ Journal : première ligne vide")'

    # A. nouveau code analytique
    t("B5", "A. Nouveau code analytique (activité ou événement)", S_SECTION)
    t("B6", "Préfixe")
    P("C6", '<c r="C6" s="18"/>')
    f("D6", 'IF($C$6="","",IFERROR(INDEX(T_Prefixes[Libellé],MATCH($C$6,T_Prefixes[Préfixe],0))&" · axe "&INDEX(T_Prefixes[Axe],MATCH($C$6,T_Prefixes[Préfixe],0)),"préfixe inconnu"))', S_NOTE)
    t("B7", "Libellé")
    P("C7", '<c r="C7" s="18"/>')
    t("B8", "Statut (axe 2)")
    P("C8", '<c r="C8" s="18"/>')
    t("D8", "1 = En cours pour un nouvel événement", S_NOTE)
    t("B9", "Code proposé")
    f("C9", 'IFERROR(INDEX(T_Prefixes[Code suivant],MATCH($C$6,T_Prefixes[Préfixe],0)),"")', S_GRAS)
    f("R6", 'IFERROR(INDEX(T_Prefixes[Axe],MATCH($C$6,T_Prefixes[Préfixe],0)),0)', texte=False)
    t("B11", "Contrôles")
    f("D11", 'IF($C$6="","Choisir un préfixe.",IF(TRIM($C$7)="","Saisir le libellé.",IF($R$6=1,IF(COUNTIF(T_Axe1[Code],$C$9)>0,'
             '"Ce code existe déjà dans l\'axe 1.",IF(COUNTIF(T_Axe1[Libellé],TRIM($C$7))>0,"Ce libellé existe déjà dans l\'axe 1.","")),'
             'IF(COUNTIF(T_Axe2[Code],$C$9)>0,"Ce code existe déjà dans l\'axe 2.",IF(COUNTIF(T_Axe2[Libellé],TRIM($C$7))>0,'
             '"Ce libellé existe déjà dans l\'axe 2.",IF($C$8="","Choisir le statut.",""))))))')
    f("C11", 'IF(AND($C$6="",$C$7=""),"",IF(D11="","OK","Erreur"))')
    t("B12", "Ligne à coller dans T_Axe (Code, Libellé, Actif)")
    f("C12", 'IF(C11="OK",$C$9,"")')
    f("D12", 'IF(C11="OK",UPPER(TRIM($C$7)),"")')
    f("E12", 'IF(C11="OK",IF($R$6=1,1,VALUE($C$8&"")),"")', texte=False)
    f("F12", 'IF(C11<>"OK","",HYPERLINK("#\'"&IF($R$6=1,"Axe 1 - Anal1","Axe 2 - Anal2")&"\'!A"&(IF($R$6=1,ROWS(T_Axe1[Code]),ROWS(T_Axe2[Code]))+2),'
             '"→ Coller C12:E12 ici (Collage spécial › Valeurs)"))', S_LIEN)
    t("B13", "Ligne à coller dans le Journal")
    for c, formule, s, texte in (("C", "TODAY()", S_DATE, False), ("D", 'CO_Auteur&""', None, True), ("E", '""', None, True),
                                 ("F", '"Création"', None, True), ("G", '"T_Axe"&$R$6&" "&$C$9', None, True), ("H", '""', None, True),
                                 ("I", 'UPPER(TRIM($C$7))', None, True)):
        f(f"{c}13", f'IF(C11="OK",{formule},"")', s, texte=texte)
    f("F14", f'IF(C11<>"OK","",{journal_zone})', S_LIEN)
    t("B14", "puis coller C13:I13 dans le Journal", S_NOTE)

    # B. nouveau membre
    t("B16", "B. Nouveau membre (compte 411)", S_SECTION)
    t("B17", "Nom")
    P("C17", '<c r="C17" s="18"/>')
    t("B18", "Prénom")
    P("C18", '<c r="C18" s="18"/>')
    cle = 'UPPER(TRIM($C$17))'
    for a, b in (("É", "E"), ("È", "E"), ("Ê", "E"), ("Ë", "E"), ("À", "A"), ("Â", "A"), ("Ä", "A"), ("Ç", "C"), ("Î", "I"),
                 ("Ï", "I"), ("Ô", "O"), ("Ö", "O"), ("Û", "U"), ("Ü", "U"), ("Ù", "U"), (" ", ""), ("-", ""), ("'", ""), ("’", "")):
        cle = f'SUBSTITUTE({cle},"{a}","{b}")'
    f("R17", f'LEFT({cle},5)')
    f("R18", 'IFERROR(INDEX(T_TypesTiers[Préfixe compte],MATCH("Membre",T_TypesTiers[Tiers],0))&"","")')
    t("B19", "Compte proposé")
    f("C19", 'IF($R$17="","",$R$18&$R$17&TEXT(COUNTIF(T_PlanComptable[Compte],$R$18&$R$17&"*")+1,"000"))', S_GRAS)
    t("B20", "Libellé du compte")
    f("C20", 'TRIM(UPPER(TRIM($C$17))&" "&UPPER(TRIM($C$18)))')
    t("B24", "Contrôles")
    f("D24", 'IF(TRIM($C$17)="","Saisir le nom.",IF(COUNTIF(T_PlanComptable[Compte],$C$19)>0,"Ce compte existe déjà : "&$C$19&".",'
             'IF(COUNTIF(T_PlanComptable[Libellé compte],$C$20)>0,"Un compte existe déjà à ce nom : "&INDEX(T_PlanComptable[Compte],'
             'MATCH($C$20,T_PlanComptable[Libellé compte],0))&".","")))')
    f("C24", 'IF(AND($C$17="",$C$18=""),"",IF(D24="","OK","Erreur"))')
    t("B25", "Ligne à coller dans T_PlanComptable")
    f("C25", 'IF(C24="OK",$C$19,"")')
    f("D25", 'IF(C24="OK",$C$20,"")')
    f("E25", 'IF(C24="OK",IFERROR(INDEX(T_PlanComptable[Axe 1 (Anal1)],MATCH($R$18&"*",T_PlanComptable[Compte],0)),""),"")')
    f("F25", 'IF(C24="OK","oui","")')
    f("G25", 'IF(C24="OK","oui","")')
    f("H25", 'IF(C24<>"OK","",HYPERLINK("#\'Plan comptable\'!A"&(ROWS(T_PlanComptable[Compte])+2),"→ Coller C25:G25 ici (Valeurs)"))', S_LIEN)
    t("B26", "Ligne à coller dans le Journal")
    for c, formule, s, texte in (("C", "TODAY()", S_DATE, False), ("D", 'CO_Auteur&""', None, True), ("E", '""', None, True),
                                 ("F", '"Création"', None, True), ("G", '"T_PlanComptable "&$C$19', None, True), ("H", '""', None, True),
                                 ("I", '$C$20', None, True)):
        f(f"{c}26", f'IF(C24="OK",{formule},"")', s, texte=texte)
    f("F27", f'IF(C24<>"OK","",{journal_zone})', S_LIEN)
    t("B27", "La fiche du membre (T_Membres) viendra au Lot 2.", S_NOTE)

    # C. statut d'un code Anal2
    t("B28", "C. Statut d'un code Anal2", S_SECTION)
    t("B29", "Code")
    P("C29", '<c r="C29" s="18"/>')
    f("D29", 'IF($C$29="","",IFERROR(INDEX(T_Axe2[Libellé],MATCH($C$29,T_Axe2[Code],0)),"Code introuvable"))', S_NOTE)
    t("B30", "Statut actuel")
    f("R30", 'IFERROR(INDEX(T_Axe2[Actif],MATCH($C$29,T_Axe2[Code],0)),"")', texte=False)
    f("C30", 'IF($R$30="","",$R$30&" – "&IFERROR(INDEX(\'Axe 2 - Anal2\'!$G$2:$G$4,MATCH($R$30,\'Axe 2 - Anal2\'!$F$2:$F$4,0)),""))')
    t("B31", "Utilisé dans")
    f("C31", 'IF($C$29="","",COUNTIF(T_Ecritures[Anal2],$C$29)&" ligne(s) d\'écritures")')
    t("B33", "Nouveau statut")
    P("C33", '<c r="C33" s="18"/>')
    f("D33", 'IF($C$33="","",IFERROR(INDEX(\'Axe 2 - Anal2\'!$G$2:$G$4,MATCH(VALUE($C$33&""),\'Axe 2 - Anal2\'!$F$2:$F$4,0)),""))', S_NOTE)
    t("B34", "Confirmation (code déjà utilisé)")
    P("C34", '<c r="C34" s="18"/>')
    t("B37", "Contrôles")
    f("D37", 'IF($C$29="","Choisir le code.",IF(COUNTIF(T_Axe2[Code],$C$29)=0,"Code inconnu.",IF($C$33="","Choisir le nouveau statut.",'
             'IF(VALUE($C$33&"")=$R$30,"Le statut est déjà "&$R$30&".",IF(AND(COUNTIF(T_Ecritures[Anal2],$C$29)>0,$C$34<>"Oui"),'
             '"Code utilisé dans "&COUNTIF(T_Ecritures[Anal2],$C$29)&" ligne(s) : confirmer avec Oui.","")))))')
    f("C37", 'IF(AND($C$29="",$C$33=""),"",IF(D37="","OK","Erreur"))')
    t("B38", "Modifier le statut")
    f("C38", 'IF(C37<>"OK","",HYPERLINK("#\'Axe 2 - Anal2\'!C"&(MATCH($C$29,T_Axe2[Code],0)+1),"→ Ouvrir la case Actif de "&$C$29&" et y choisir "&$C$33))', S_LIEN)
    t("B39", "Ligne à coller dans le Journal")
    for c, formule, s, texte in (("C", "TODAY()", S_DATE, False), ("D", 'CO_Auteur&""', None, True), ("E", '""', None, True),
                                 ("F", '"Statut"', None, True), ("G", '"T_Axe2 "&$C$29', None, True), ("H", '$C$30', None, True),
                                 ("I", '$C$33&" – "&$D$33', None, True)):
        f(f"{c}39", f'IF(C37="OK",{formule},"")', s, texte=texte)
    f("F40", f'IF(C37<>"OK","",{journal_zone})', S_LIEN)
    fe.enregistrer()
    cl.dimension(part)
    cl.journal.append(("Ajout", "onglet Codes", "", "nouveau code analytique, nouveau membre, statut d'un code Anal2"))
    return part


# ---------------------------------------------------------------- accueil, compte rendu, journal

def accueil_compte_rendu_journal(cl):
    p, ch = cl.p, cl.ch
    f = feuilles(p)
    fe = Feuille(p, f["Accueil"])
    menu = [(34, "Saisie", "Saisie guidée d'une opération (Lot 1)"),
            (35, "Codes", "Nouveau code analytique, nouveau membre, statut d'un code Anal2"),
            (36, "Modèles", "Types d'opérations et moyens de paiement (paramètres de la saisie)")]
    liens = ""
    for r, nom, desc in menu:
        fe.poser(f"B{r}", c_texte(f"B{r}", ch, "→ " + nom, 35))
        fe.poser(f"C{r}", c_texte(f"C{r}", ch, desc, 36))
        liens += f'<hyperlink ref="B{r}" location="\'{nom}\'!A1" display="→ {nom}"/>'
    fe.remplacer("</hyperlinks>", liens + "</hyperlinks>")
    fe.remplacer('<dimension ref="A1:E33"/>', '<dimension ref="A1:E36"/>')
    fe.enregistrer()

    fe = Feuille(p, f["Compte rendu"])
    s44 = re.search(r' s="(\d+)"', fe.cellule("C44")).group(1)
    fe.poser("C44", c_texte("C44", ch, "Onglet Saisie : remplir les cases jaunes ; quand tous les contrôles sont OK, copier les lignes "
                                       "vertes et les coller en valeurs sous la table Écritures (instruction affichée dans l'onglet).", s44))
    lignes = [
        ("A57", "7. Lot 1 – Saisie guidée (26/09/2026)", 55),
        ("B58", "Saisie", "Onglet Saisie : 14 types d'opérations, écritures générées selon les conventions existantes (un Mvt de 4 lignes "
                          "facture + règlement dans le journal du paiement), 11 contrôles bloquants, lignes prêtes à coller."),
        ("B59", "Paramètres", "Onglet Modèles : types d'opérations, schémas d'écritures, moyens de paiement ; tout se modifie sans toucher aux formules."),
        ("B60", "Codes", "Onglet Codes : code analytique proposé d'après le préfixe, compte de nouveau membre, changement de statut Anal2 "
                         "avec confirmation si le code est utilisé ; chaque action prépare sa ligne de Journal."),
    ]
    for item in lignes:
        if isinstance(item[2], int):
            fe.poser(item[0], c_texte(item[0], ch, item[1], item[2]))
            fe.lignes[int(item[0][1:])][0] = ' ht="15.75" x14ac:dyDescent="0.2"'
        else:
            r = item[0][1:]
            fe.poser(f"B{r}", c_texte(f"B{r}", ch, item[1], 59))
            fe.poser(f"C{r}", c_texte(f"C{r}", ch, item[2], 54))
    fe.remplacer('<dimension ref="A1:D55"/>', '<dimension ref="A1:D60"/>')
    fe.enregistrer()

    # Journal des modifications : lignes ajoutées sous T_Journal
    t = tables(p)["T_Journal"]
    tx = p.lire(t)
    fin = int(re.search(r'ref="A4:G(\d+)"', tx).group(1))
    fe = Feuille(p, f["Journal des modifications"])
    for k, (action, objet, avant, apres) in enumerate(cl.journal):
        r = fin + 1 + k
        fe.poser(f"A{r}", c_nombre(f"A{r}", serial(AUJOURDHUI), S_DATE))
        for c, v in (("B", AUTEUR), ("C", "Lot 1"), ("D", action), ("E", objet), ("F", avant), ("G", apres)):
            if v:
                fe.poser(f"{c}{r}", c_texte(f"{c}{r}", ch, v))
    nouvelle_fin = fin + len(cl.journal)
    fe.remplacer(f'<dimension ref="A1:I{fin}"/>', f'<dimension ref="A1:I{nouvelle_fin}"/>')
    fe.enregistrer()
    p.ecrire(t, tx.replace(f'A4:G{fin}"', f'A4:G{nouvelle_fin}"'))


def maj_app(p):
    wb = p.lire("xl/workbook.xml")
    app = p.lire("docProps/app.xml")
    feuilles_ = re.findall(r'<sheet name="([^"]+)"', wb)
    noms = re.findall(r'<definedName name="([^"]+)"(?![^>]*hidden="1")([^>]*)>', wb)
    titres = [n for n in feuilles_]
    for n, attrs in noms:
        m = re.search(r'localSheetId="(\d+)"', attrs)
        titres.append(f"'{feuilles_[int(m.group(1))]}'!{n}" if m else n)
    app = re.sub(r"(<vt:lpstr>Feuilles de calcul</vt:lpstr></vt:variant><vt:variant><vt:i4>)\d+", rf"\g<1>{len(feuilles_)}", app)
    app = re.sub(r"(<vt:lpstr>Plages nommées</vt:lpstr></vt:variant><vt:variant><vt:i4>)\d+", rf"\g<1>{len(noms)}", app)
    app = re.sub(r'<TitlesOfParts><vt:vector size="\d+" baseType="lpstr">.*?</vt:vector></TitlesOfParts>',
                 f'<TitlesOfParts><vt:vector size="{len(titres)}" baseType="lpstr">' + "".join(f"<vt:lpstr>{t}</vt:lpstr>" for t in titres)
                 + "</vt:vector></TitlesOfParts>", app, flags=re.S)
    p.ecrire("docProps/app.xml", app)


def remplir(cl, entrees):
    """Tests : pose des valeurs dans les cases jaunes ({"Saisie!C4": valeur, …})."""
    f = feuilles(cl.p)
    par_onglet = {}
    for ref, v in entrees.items():
        onglet, cellule = ref.split("!")
        par_onglet.setdefault(onglet, {})[cellule] = v
    for onglet, cellules in par_onglet.items():
        fe = Feuille(cl.p, f[onglet])
        for cellule, v in cellules.items():
            s = re.search(r' s="(\d+)"', fe.cellule(cellule) or "")
            s = s.group(1) if s else None
            fe.poser(cellule, c_nombre(cellule, v, s) if isinstance(v, (int, float)) else c_texte(cellule, cl.ch, v, s))
        fe.enregistrer()


def main(entree, sortie, entrees=None):
    cl = Classeur(entree)
    onglet_modeles(cl)
    onglet_saisie(cl)
    onglet_codes(cl)
    cl.enregistrer_noms()
    accueil_compte_rendu_journal(cl)
    if entrees:
        remplir(cl, entrees)
    cl.ch.enregistrer()
    maj_app(cl.p)
    cl.p.enregistrer(sortie)
    print(f"{sortie} : Lot 1 appliqué ({len(cl.journal)} lignes de journal)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
