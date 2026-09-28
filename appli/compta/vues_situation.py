"""Situation financière : le tableau de bord mis en page pour une présentation (bureau, assemblée), en PDF et en Excel."""

import datetime as dt
import io

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import render

from . import controles as ctrl
from . import etats
from .models import ZERO, Journal, Mouvement, Reglage, arrondi, soldes
from .views import lignes_periode, periode, resultat_par_axe

consulter = permission_required("compta.view_mouvement", raise_exception=True)


def par_compte(lignes, classe):
    """Comptes de la classe 6 (charges) ou 7 (produits) : [(compte, libellé, montant)], du plus grand au plus petit."""
    sens = (F("debit") - F("credit")) if classe == "6" else (F("credit") - F("debit"))
    rows = (lignes.filter(compte__numero__startswith=classe).values("compte_id", "compte__libelle")
            .annotate(m=Sum(sens)).order_by("-m"))
    return [(r["compte_id"], r["compte__libelle"], arrondi(r["m"])) for r in rows if arrondi(r["m"])]


def donnees(debut, fin):
    ls = lignes_periode(debut, fin)
    _, _, charges = soldes(ls.filter(compte__numero__startswith="6"))
    _, _, produits = soldes(ls.filter(compte__numero__startswith="7"))
    tresorerie = [{"journal": j, "solde": etats.solde_cumule(j.compte, fin)}
                  for j in Journal.objects.filter(compte__isnull=False).select_related("compte")]
    etat, a_verifier = ctrl.etat_general(ctrl.executer())
    return {
        "debut": debut, "fin": fin, "edite_le": dt.datetime.now(),
        "association": Reglage.lire("nom_association", "") or Reglage.lire("association", ""),
        "produits": -produits, "charges": charges, "resultat": -(produits + charges),
        "tresorerie": tresorerie, "total_tresorerie": sum((t["solde"] for t in tresorerie), ZERO),
        "axe1": resultat_par_axe(ls, 1), "axe2": [a for a in resultat_par_axe(ls, 2) if a["produits"] or a["charges"]],
        "charges_par_compte": par_compte(ls, "6"), "produits_par_compte": par_compte(ls, "7"),
        "nb_mouvements": Mouvement.objects.filter(date__range=(debut, fin)).count(), "etat": etat, "a_verifier": a_verifier,
    }


@login_required
@consulter
def situation(request):
    debut, fin = periode(request)
    return render(request, "compta/situation.html", donnees(debut, fin))


@login_required
@consulter
def situation_excel(request):
    debut, fin = periode(request)
    d = donnees(debut, fin)
    wb = classeur(d)
    tampon = io.BytesIO()
    wb.save(tampon)
    nom = f"Situation_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx"
    r = HttpResponse(tampon.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = f'attachment; filename="{nom}"'
    return r


def classeur(d):
    """Une feuille « Situation » mise en page (A4 portrait, prête à imprimer) et les détails par compte."""
    import openpyxl
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.page import PageMargins

    BLEU, CLAIR, GRIS = "1F3864", "EEF3FB", "DDE1E7"
    MONTANT = '#,##0.00 "₪";[Red]-#,##0.00 "₪";"–"'
    titre_f, sous_f = Font(bold=True, size=18, color=BLEU), Font(size=11, color="555555")
    section_f, entete_f = Font(bold=True, size=13, color=BLEU), Font(bold=True, color="FFFFFF")
    fond_entete, fond_clair, fond_total = (PatternFill("solid", fgColor=BLEU), PatternFill("solid", fgColor=CLAIR),
                                           PatternFill("solid", fgColor=GRIS))
    trait = Side(style="thin", color=GRIS)
    bas = Border(bottom=trait)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Situation"
    ws.sheet_view.showGridLines = False
    for col, largeur in zip("ABCDE", (14, 38, 17, 17, 17)):
        ws.column_dimensions[col].width = largeur
    ligne = [1]

    def ecrire(valeurs, police=None, fond=None, montants=(), bordure=None, hauteur=None):
        r = ligne[0]
        for i, v in enumerate(valeurs, 1):
            c = ws.cell(r, i, v)
            if police:
                c.font = police
            if fond:
                c.fill = fond
            if bordure:
                c.border = bordure
            if i in montants:
                c.number_format = MONTANT
                c.alignment = Alignment(horizontal="right")
        if hauteur:
            ws.row_dimensions[r].height = hauteur
        ligne[0] += 1
        return r

    def section(titre):
        ligne[0] += 1
        r = ecrire([titre], police=section_f, hauteur=22)
        ws.cell(r, 1).border = Border(bottom=Side(style="medium", color=BLEU))
        for i in range(2, 6):
            ws.cell(r, i).border = Border(bottom=Side(style="medium", color=BLEU))

    def tableau(entetes, lignes, montants, total=None):
        ecrire(entetes, police=entete_f, fond=fond_entete)
        for k, l in enumerate(lignes):
            ecrire(l, fond=fond_clair if k % 2 else None, montants=montants, bordure=bas)
        if total:
            ecrire(total, police=Font(bold=True), fond=fond_total, montants=montants)

    ecrire(["Situation financière" + (f" – {d['association']}" if d["association"] else "")], police=titre_f, hauteur=30)
    ecrire([f"Période du {d['debut']:%d/%m/%Y} au {d['fin']:%d/%m/%Y} · éditée le {d['edite_le']:%d/%m/%Y à %H:%M}"],
           police=sous_f)

    section("Chiffres clés")
    tableau(["", "Indicateur", "Montant"],
            [["", "Produits", d["produits"]], ["", "Charges", d["charges"]], ["", "Résultat", d["resultat"]],
             ["", f"Trésorerie au {d['fin']:%d/%m/%Y}", d["total_tresorerie"]]], montants=(3,))
    ecrire(["", f"{d['nb_mouvements']} mouvements sur la période · contrôles : {d['etat']}"
            + (f" ({d['a_verifier']} à vérifier)" if d["a_verifier"] else "")], police=sous_f)

    section("Trésorerie")
    tableau(["Journal", "Compte", "Solde"],
            [[t["journal"].code, f"{t['journal'].compte_id} – {t['journal'].compte.libelle}", t["solde"]] for t in d["tresorerie"]],
            montants=(3,), total=["Total", "", d["total_tresorerie"]])

    for titre, cle in (("Résultat par activité (axe 1)", "axe1"), ("Résultat par événement / projet (axe 2)", "axe2")):
        section(titre)
        ls = d[cle]
        tableau(["Code", "Libellé", "Produits", "Charges", "Résultat"],
                [[a["code"] or "(sans code)", a["libelle"] or "", a["produits"], a["charges"], a["resultat"]] for a in ls],
                montants=(3, 4, 5),
                total=["Total", "", sum((a["produits"] for a in ls), ZERO), sum((a["charges"] for a in ls), ZERO),
                       sum((a["resultat"] for a in ls), ZERO)])

    for titre, cle, total in (("Produits par compte", "produits_par_compte", d["produits"]),
                              ("Charges par compte", "charges_par_compte", d["charges"])):
        section(titre)
        tableau(["Compte", "Libellé", "Montant", "Part"],
                [[c, lib, m, float(m / total) if total else None] for c, lib, m in d[cle]], montants=(3,),
                total=["Total", "", total, 1 if total else None])
        for r in range(ligne[0] - len(d[cle]) - 1, ligne[0]):
            ws.cell(r, 4).number_format = "0.0 %"

    ws.print_title_rows = None
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.6, bottom=0.6)
    ws.oddFooter.center.text = "Page &P / &N"
    ws.oddFooter.right.text = f"Situation au {d['fin']:%d/%m/%Y}"
    return wb
