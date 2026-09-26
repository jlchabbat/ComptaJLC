"""Lot 1 (2e partie) — transmission des saisies à distance, libellés d'axes, protection.

    python src/lot1_distance.py ComptaBB_lot1.xlsm ComptaBB.xlsm

S'applique au classeur produit par `lot1_saisie.py`.

- **Transmission** : le trésorier colle dans T_Recu les lignes de l'onglet
  Envoi d'un classeur de saisie externe (`classeur_saisie.py`). Chaque ligne
  est contrôlée, les Mvt et pièces reçoivent leur numéro définitif, et les
  lignes à reporter sous T_Ecritures s'affichent quand tout est OK.
- **Libellé Axe1** dans le plan comptable (T_PlanComptable).
- **Protection sans mot de passe** des onglets de consultation et de saisie :
  seules les cases jaunes restent modifiables. Les onglets dont les tables
  s'allongent (Écritures, référentiels, Journal, Transmission…) ne sont pas
  protégés, car une table ne s'agrandit pas dans un onglet protégé.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lot0_preparation import Feuille, c_texte, feuilles, tables, x  # noqa: E402
from lot1_saisie import (  # noqa: E402
    DXF_ERREUR, DXF_OK, S_DATE, S_ENTETE, S_GRAS, S_LIEN, S_MONTANT, S_NOTE, S_SECTION, S_SOUS_SECTION, S_TITRE,
    Classeur, c_f, lettre, maj_app, remplir,
)

NB_RECU = 60             # lignes reçues reportables en une fois
L_RECU = 7               # première ligne de données de T_Recu
COLONNES = ["Date", "Jnl", "Mvt", "Pièce", "Compte", "Intitulé", "Libellé", "Débit", "Crédit", "Solde", "Anal1", "Anal2", "Let"]
ONGLETS_PROTEGES = ["Accueil", "Saisie", "Codes", "Compte rendu", "CDC ComptaBB", "Tableau de bord", "Synthèse", "Contrôles",
                    "Consultation", "Jnl Banque B1", "Jnl Banque B2", "Jnl Banque B3", "Jnl Caisse", "Banque1"]
A_DEVERROUILLER = {"Banque1": ["B6"]}   # saisies sans le style jaune


def onglet_transmission(cl, recu=None):
    ch = cl.ch
    recu = recu or [[None] * len(COLONNES)]
    rang = ('SUMPRODUCT((T_Recu[Mvt]<T_Recu[[#This Row],[Mvt]])*(T_Recu[Mvt]<>"")'
            '/(COUNTIF(T_Recu[Mvt],T_Recu[Mvt])+(T_Recu[Mvt]="")))+1')
    calculees = {
        "Mvt définitif": f'IF(T_Recu[[#This Row],[Mvt]]="","",MAX(T_Ecritures[Mvt])+{rang})',
        "Pièce définitive": f'IF(T_Recu[[#This Row],[Mvt]]="","",MAX(T_Ecritures[Pièce])+{rang})',
        "Contrôle": ('IF(T_Recu[[#This Row],[Date]]="","",'
                     'IF(NOT(ISNUMBER(T_Recu[[#This Row],[Date]])),"Date invalide | ",IF(T_Recu[[#This Row],[Date]]<=P_DateCloture,'
                     '"Période close | ",IF(OR(T_Recu[[#This Row],[Date]]<P_DebutExercice,T_Recu[[#This Row],[Date]]>P_FinExercice),'
                     '"Hors exercice | ","")))'
                     '&IF(COUNTIF(L_Journaux,T_Recu[[#This Row],[Jnl]])=0,"Journal inconnu | ","")'
                     '&IF(COUNTIF(L_Comptes,T_Recu[[#This Row],[Compte]])=0,"Compte inconnu | ","")'
                     '&IF(COUNTIF(L_Anal2,T_Recu[[#This Row],[Anal2]])=0,"Anal2 inconnu | ","")'
                     '&IF((N(T_Recu[[#This Row],[Débit]])<>0)=(N(T_Recu[[#This Row],[Crédit]])<>0),"Débit/Crédit | ","")'
                     '&IF(ROUND(SUMIFS(T_Recu[Débit],T_Recu[Mvt],T_Recu[[#This Row],[Mvt]])-SUMIFS(T_Recu[Crédit],T_Recu[Mvt],'
                     'T_Recu[[#This Row],[Mvt]]),2)<>0,"Mvt déséquilibré | ","")'
                     '&IF(COUNTIFS(T_Ecritures[Date],T_Recu[[#This Row],[Date]],T_Ecritures[Compte],T_Recu[[#This Row],[Compte]],'
                     'T_Ecritures[Libellé],T_Recu[[#This Row],[Libellé]],T_Ecritures[Débit],T_Recu[[#This Row],[Débit]],'
                     'T_Ecritures[Crédit],T_Recu[[#This Row],[Crédit]])>0,"Déjà dans Écritures | ",""))'),
    }
    cf = (f'<conditionalFormatting sqref="P{L_RECU}:P{L_RECU + 500}"><cfRule type="expression" dxfId="{DXF_ERREUR}" priority="1">'
          f'<formula>$P{L_RECU}&lt;&gt;""</formula></cfRule></conditionalFormatting>'
          f'<conditionalFormatting sqref="A3"><cfRule type="expression" dxfId="{DXF_OK}" priority="2"><formula>TR_OK</formula></cfRule>'
          f'<cfRule type="expression" dxfId="{DXF_ERREUR}" priority="3"><formula>AND(TR_Nb&gt;0,NOT(TR_OK))</formula></cfRule></conditionalFormatting>'
          f'<conditionalFormatting sqref="T{L_RECU}:AF{L_RECU + NB_RECU - 1}"><cfRule type="expression" dxfId="{DXF_OK}" priority="4">'
          f'<formula>$T{L_RECU}&lt;&gt;""</formula></cfRule></conditionalFormatting>')
    largeurs = ([(1, 1, 11, 0), (2, 2, 5, 0), (3, 4, 7, 0), (5, 5, 13, 0), (6, 6, 5, 0), (7, 7, 36, 0), (8, 10, 10, 0),
                 (11, 11, 5, 0), (12, 12, 9, 0), (13, 13, 4, 0), (14, 15, 10, 0), (16, 16, 30, 0), (17, 17, 3, 0),
                 (18, 18, 8, 1), (19, 19, 3, 0), (20, 20, 11, 0), (21, 21, 5, 0), (22, 23, 7, 0), (24, 24, 13, 0),
                 (25, 25, 5, 0), (26, 26, 36, 0), (27, 29, 10, 0), (30, 30, 5, 0), (31, 31, 9, 0), (32, 32, 5, 0)])
    part = cl.nouvel_onglet("Transmission", "Codes", largeurs, cf=cf, n_tables=1,
                            vue=f'<pane ySplit="{L_RECU - 1}" topLeftCell="A{L_RECU}" activePane="bottomLeft" state="frozen"/>'
                                f'<selection pane="bottomLeft" activeCell="A{L_RECU}" sqref="A{L_RECU}"/>',
                            liens='<hyperlink ref="P1" location="\'Accueil\'!A1" tooltip="Retour au menu" display="← Accueil"/>')
    cl.nouvelle_table(part, "rId1", "T_Recu", f"A{L_RECU - 1}", COLONNES + list(calculees), [ligne + [None] * 3 for ligne in recu],
                      calculees=calculees, styles={"Date": S_DATE, "Débit": S_MONTANT, "Crédit": S_MONTANT, "Solde": S_MONTANT})
    fe = Feuille(cl.p, part)

    def t(ref, texte, s=None):
        fe.poser(ref, c_texte(ref, ch, texte, s))

    def f(ref, formule, s=None, texte=True):
        fe.poser(ref, c_f(ref, formule, s, texte=texte))

    t("A1", "Transmission : lignes reçues d'un saisisseur", S_TITRE)
    t("P1", "← Accueil", S_LIEN)
    t("A2", "1. Dans le classeur de saisie reçu, onglet Envoi : copier les lignes de la table. 2. Ici : clic droit sur A7 › Collage "
            "spécial › Valeurs (la table s'agrandit). 3. Corriger ce que la colonne Contrôle signale. 4. Reporter les lignes vertes "
            "(à droite) sous Écritures, puis vider la table et noter la transmission au Journal.", S_NOTE)
    f("A3", 'IF(TR_Nb=0,"Coller ici, en A7, les lignes reçues (onglet Envoi du classeur de saisie).",IF(ROWS(T_Recu[Date])>TR_Nb,'
            '"Supprimer les lignes vides de la table (clic droit › Supprimer › Lignes du tableau).",IF(TR_OK,"PRÊT À REPORTER : "&TR_Nb'
            '&" lignes, Mvt "&MIN(T_Recu[Mvt définitif])&" à "&MAX(T_Recu[Mvt définitif]),"À CORRIGER : "&TR_Err&" ligne(s) signalée(s) '
            'dans la colonne Contrôle.")))', S_GRAS)
    f("A4", f'IF(NOT(TR_OK),"","Sélectionner T{L_RECU}:AF"&({L_RECU - 1}+TR_Nb)&", Copier ; dans Écritures, cellule A"'
            '&(ROWS(T_Ecritures[Date])+2)&" : Collage spécial › Valeurs, en cochant « Blancs non compris ». Puis supprimer les lignes '
            'de T_Recu (clic droit › Supprimer › Lignes du tableau) et coller la ligne de Journal (T3:Z3).")', S_NOTE)
    # calculs nommés (colonne R masquée)
    for r, nom, formule in ((2, "TR_Nb", "COUNT(T_Recu[Date])"), (3, "TR_Err", 'COUNTIF(T_Recu[Contrôle],"?*")'),
                            (4, "TR_OK", "AND(TR_Nb>0,TR_Err=0,ROWS(T_Recu[Date])=TR_Nb)")):
        f(f"R{r}", formule, texte=False)
        cl.nommer(nom, f"Transmission!$R${r}")
    # ligne de journal
    t("T2", "Ligne à coller dans le Journal des modifications", S_SOUS_SECTION)
    for c, formule, s, texte in (("T", "TODAY()", S_DATE, False), ("U", 'CO_Auteur&""', None, True), ("V", '""', None, True),
                                 ("W", '"Transmission"', None, True),
                                 ("X", '"Mvt "&MIN(T_Recu[Mvt définitif])&" à "&MAX(T_Recu[Mvt définitif])', None, True),
                                 ("Y", '""', None, True), ("Z", 'TR_Nb&" lignes reçues"', None, True)):
        f(f"{c}3", f'IF(TR_OK,{formule},"")', s, texte=texte)
    f("AB3", 'IF(NOT(TR_OK),"",HYPERLINK("#\'Journal des modifications\'!A"&(ROWS(T_Journal[Date])+5),"→ Journal"))', S_LIEN)
    f("AB5", 'HYPERLINK("#\'Écritures\'!A"&(ROWS(T_Ecritures[Date])+2),"→ Écritures : première ligne vide")', S_LIEN)
    # lignes à reporter : mêmes colonnes que T_Ecritures ; Intitulé, Anal1, Let laissés vides
    t("T5", "Lignes à reporter dans Écritures", S_SECTION)
    source = {"Date": "Date", "Jnl": "Jnl", "Mvt": "Mvt définitif", "Pièce": "Pièce définitive", "Compte": "Compte",
              "Libellé": "Libellé", "Débit": "Débit", "Crédit": "Crédit", "Anal2": "Anal2"}
    for j, h in enumerate(COLONNES):
        ref = f"{lettre(20 + j)}{L_RECU - 1}"
        t(ref, {"Intitulé": "(calculé)", "Anal1": "(calculé)", "Let": "(vide)"}.get(h, h), S_ENTETE)
    for i in range(1, NB_RECU + 1):
        r = L_RECU + i - 1
        f(f"R{r}", f'IF({i}>ROWS(T_Recu[Date]),0,IF(INDEX(T_Recu[Date],{i})="",0,{i}))', texte=False)
        for j, h in enumerate(COLONNES):
            c = lettre(20 + j)
            if h in source:
                s = {"Date": S_DATE, "Débit": S_MONTANT, "Crédit": S_MONTANT}.get(h)
                f(f"{c}{r}", f'IF(AND(TR_OK,$R{r}>0),INDEX(T_Recu[{source[h]}],$R{r}),"")', s,
                  texte=h in ("Jnl", "Compte", "Libellé", "Anal2"))
            elif h == "Solde":
                f(f"{c}{r}", f'IF(AND(TR_OK,$R{r}>0),0,"")', S_MONTANT, texte=False)
    fe.enregistrer()
    cl.dimension(part)
    cl.journal.append(("Ajout", "onglet Transmission", "", "T_Recu : lignes reçues contrôlées, renumérotées et prêtes à reporter"))
    return part


def libelle_axe1_plan(cl):
    p, ch = cl.p, cl.ch
    t = tables(p)["T_PlanComptable"]
    tx = p.lire(t)
    fin = int(re.search(r'ref="A1:G(\d+)"', tx).group(1))
    formule = ('IF(T_PlanComptable[[#This Row],[Axe 1 (Anal1)]]="","",IFERROR(INDEX(T_Axe1[Libellé],'
               'MATCH(T_PlanComptable[[#This Row],[Axe 1 (Anal1)]],T_Axe1[Code],0)),"Code introuvable"))')
    tx = tx.replace(f'ref="A1:G{fin}"', f'ref="A1:H{fin}"')
    n = int(re.search(r'<tableColumns count="(\d+)"', tx).group(1))
    tx = re.sub(r'<tableColumns count="\d+">', f'<tableColumns count="{n + 1}">', tx)
    tx = tx.replace("</tableColumns>", f'<tableColumn id="{n + 1}" name="Libellé Axe1"><calculatedColumnFormula>{x(formule)}'
                                       "</calculatedColumnFormula></tableColumn></tableColumns>")
    p.ecrire(t, tx)
    fe = Feuille(p, feuilles(p)["Plan comptable"])
    fe.poser("H1", c_texte("H1", ch, "Libellé Axe1"))
    for r in range(2, fin + 1):
        fe.poser(f"H{r}", c_f(f"H{r}", formule))
    fe.remplacer("</cols>", '<col min="8" max="8" width="24" customWidth="1"/></cols>', obligatoire=False)
    fe.enregistrer()
    cl.journal.append(("Ajout", "T_PlanComptable[Libellé Axe1]", "", "libellé de l'axe 1 calculé depuis T_Axe1"))


def _deverrouille(xf):
    if xf.endswith("/>"):
        return xf[:-2] + ' applyProtection="1"><protection locked="0"/></xf>'
    return xf.replace("<xf ", '<xf applyProtection="1" ', 1).replace("</xf>", '<protection locked="0"/></xf>')


def proteger(cl):
    p = cl.p
    st = p.lire("xl/styles.xml")
    m = re.search(r'<cellXfs count="(\d+)">(.*?)</cellXfs>', st, re.S)
    xfs = re.findall(r'<xf [^>]*?(?:/>|>.*?</xf>)', m.group(2), re.S)
    correspondance = {}

    def clone(i):
        if i not in correspondance:
            correspondance[i] = len(xfs)
            xfs.append(_deverrouille(xfs[i]))
        return correspondance[i]

    saisie = {i for i, xf in enumerate(xfs) if 'fillId="3"' in xf}
    f = feuilles(p)
    for nom in ONGLETS_PROTEGES:
        part = f[nom]
        s = p.lire(part)
        debut, fin = s.index("<sheetData"), s.index("</sheetData>")

        def deverrouiller(mc):
            cel = mc.group(0)
            ref, st_ = mc.group(1), re.search(r' s="(\d+)"', cel)
            base = int(st_.group(1)) if st_ else 0
            jaune_sans_formule = base in saisie and "<f" not in cel
            if jaune_sans_formule or ref in A_DEVERROUILLER.get(nom, []):
                n = clone(base)
                cel = cel.replace(st_.group(0), f' s="{n}"', 1) if st_ else cel.replace(f'<c r="{ref}"', f'<c r="{ref}" s="{n}"', 1)
            return cel
        corps = re.sub(r'<c r="([A-Z]+\d+)"[^>]*?(?:/>|>.*?</c>)', deverrouiller, s[debut:fin], flags=re.S)
        s = s[:debut] + corps + s[fin:]
        fin = s.index("</sheetData>") + len("</sheetData>")
        if s[fin:].startswith("<sheetCalcPr"):
            fin = s.index("/>", fin) + 2
        s = s[:fin] + '<sheetProtection sheet="1" objects="1" scenarios="1" autoFilter="0" sort="0"/>' + s[fin:]
        p.ecrire(part, s)
    p.ecrire("xl/styles.xml", st.replace(m.group(0), f'<cellXfs count="{len(xfs)}">' + "".join(xfs) + "</cellXfs>"))
    cl.journal.append(("Protection", ", ".join(ONGLETS_PROTEGES), "", "sans mot de passe ; cases jaunes modifiables "
                       "(Révision › Ôter la protection pour modifier le reste)"))


def main(entree, sortie, recu=None, entrees=None):
    cl = Classeur(entree)
    onglet_transmission(cl, recu)
    libelle_axe1_plan(cl)
    cl.enregistrer_noms()
    proteger(cl)
    menu_et_journal(cl)
    if entrees:
        remplir(cl, entrees)
    cl.ch.enregistrer()
    maj_app(cl.p)
    cl.p.enregistrer(sortie)
    print(f"{sortie} : Lot 1 (2e partie) appliqué ({len(cl.journal)} lignes de journal)")


def menu_et_journal(cl):
    p, ch = cl.p, cl.ch
    f = feuilles(p)
    fe = Feuille(p, f["Accueil"])
    fe.poser("B37", c_texte("B37", ch, "→ Transmission", 35))
    fe.poser("C37", c_texte("C37", ch, "Lignes reçues d'un saisisseur à distance : contrôle et report", 36))
    fe.remplacer("</hyperlinks>", '<hyperlink ref="B37" location="\'Transmission\'!A1" display="→ Transmission"/></hyperlinks>')
    fe.remplacer('<dimension ref="A1:E36"/>', '<dimension ref="A1:E37"/>')
    fe.enregistrer()
    fe = Feuille(p, f["Compte rendu"])
    lignes = [("B61", "Saisie à distance", "Classeur de saisie ComptaBB_Saisie.xlsx (sans grand livre) ; le trésorier colle les lignes "
                                           "reçues dans l'onglet Transmission, qui les contrôle et leur donne leur numéro définitif."),
              ("B62", "Protection", "Onglets de consultation et de saisie protégés sans mot de passe : seules les cases jaunes sont modifiables.")]
    for ref, lib, texte in lignes:
        r = ref[1:]
        fe.poser(f"B{r}", c_texte(f"B{r}", ch, lib, 59))
        fe.poser(f"C{r}", c_texte(f"C{r}", ch, texte, 54))
    fe.remplacer('<dimension ref="A1:D60"/>', '<dimension ref="A1:D62"/>')
    fe.enregistrer()
    # journal : réutilise l'ajout de lignes du Lot 1 sans retoucher Accueil ni Compte rendu
    _journal(cl)


def _journal(cl):
    import lot0_preparation as l0
    p, ch = cl.p, cl.ch
    t = tables(p)["T_Journal"]
    tx = p.lire(t)
    fin = int(re.search(r'ref="A4:G(\d+)"', tx).group(1))
    fe = Feuille(p, feuilles(p)["Journal des modifications"])
    for k, (action, objet, avant, apres) in enumerate(cl.journal):
        r = fin + 1 + k
        fe.poser(f"A{r}", l0.c_nombre(f"A{r}", l0.serial(l0.AUJOURDHUI), S_DATE))
        for c, v in (("B", "Claude Code (Lot 1)"), ("C", "Lot 1"), ("D", action), ("E", objet), ("F", avant), ("G", apres)):
            if v:
                fe.poser(f"{c}{r}", c_texte(f"{c}{r}", ch, v))
    nouvelle_fin = fin + len(cl.journal)
    fe.remplacer(f'<dimension ref="A1:I{fin}"/>', f'<dimension ref="A1:I{nouvelle_fin}"/>')
    fe.enregistrer()
    p.ecrire(t, tx.replace(f'A4:G{fin}"', f'A4:G{nouvelle_fin}"'))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

