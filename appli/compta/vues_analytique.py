"""Rapports analytiques (Consulter › Analytique) : synthèse par code d'axe 1 et d'axe 2, et détail d'un code ou de
tous les codes d'un axe (sous-totaux par compte, écritures), à l'écran, à l'impression et en Excel.

Axe 1 = code du compte (nature) ; axe 2 = code de la ligne (événement, projet). Deux familles de comptes, jamais
mélangées :
- gestion (classes 6 et 7) : produit = crédit − débit d'un compte 7, charge = débit − crédit d'un compte 6, résultat ;
- bilan (classes 1 à 5) : débit, crédit et solde (débit − crédit) des mouvements de la période."""

from collections import OrderedDict

import openpyxl
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Sum
from django.shortcuts import render

from .export import feuille
from .models import ZERO, CodeAnalytique, arrondi
from .views import lignes_periode, periode
from .vues_journaux import reponse_excel

consulter = permission_required("compta.view_mouvement", raise_exception=True)
SANS_CODE = "(sans code)"
AXES = {1: "Axe 1 – nature", 2: "Axe 2 – événement ou projet"}
NATURES = {
    "gestion": {"titre": "Gestion (comptes 6 et 7)", "colonnes": ("Produits", "Charges", "Résultat"), "classes": "67"},
    "bilan": {"titre": "Bilan (comptes 1 à 5)", "colonnes": ("Débit", "Crédit", "Solde"), "classes": "12345"},
}


def nature_choisie(request):
    return "bilan" if request.GET.get("comptes") == "bilan" else "gestion"


def filtre_classes(nature):
    q = Q()
    for c in NATURES[nature]["classes"]:
        q |= Q(compte__numero__startswith=c)
    return q


def montants(nature, compte, debit, credit):
    """(colonne a, colonne b) d'une ligne : produit et charge (gestion), débit et crédit (bilan)."""
    if nature == "bilan":
        return arrondi(debit), arrondi(credit)
    if compte.startswith("7"):
        return arrondi(credit - debit), ZERO
    return ZERO, arrondi(debit - credit)


def _total(lignes):
    a = sum((l["a"] for l in lignes), ZERO)
    b = sum((l["b"] for l in lignes), ZERO)
    return {"a": a, "b": b, "s": a - b}


def synthese(debut, fin, nature):
    res = []
    for axe in (1, 2):
        champ = "compte__anal1" if axe == 1 else "anal2"
        rows = (lignes_periode(debut, fin).filter(filtre_classes(nature))
                .values(champ, f"{champ}__libelle", "compte__numero").annotate(d=Sum("debit"), c=Sum("credit")))
        codes = OrderedDict()
        for r in sorted(rows, key=lambda r: (r[champ] is not None, r[champ] or "")):
            code = r[champ] or SANS_CODE
            x = codes.setdefault(code, {"code": code, "libelle": r[f"{champ}__libelle"] or "", "a": ZERO, "b": ZERO})
            a, b = montants(nature, r["compte__numero"], r["d"] or ZERO, r["c"] or ZERO)
            x["a"] += a
            x["b"] += b
        lignes = list(codes.values())
        for x in lignes:
            x["s"] = x["a"] - x["b"]
        res.append({"axe": axe, "titre": AXES[axe], "lignes": lignes, "total": _total(lignes)})
    return res


def detail(debut, fin, axe, nature, code=None):
    """[{code, libelle, comptes: [{numero, libelle, a, b, s}], ecritures: [...], total}] pour un axe."""
    champ = "compte__anal1" if axe == 1 else "anal2"
    qs = (lignes_periode(debut, fin).filter(filtre_classes(nature))
          .select_related("mouvement", "compte", "compte__anal1", "anal2")
          .order_by(champ, "mouvement__date", "mouvement__numero", "ordre"))
    if code == SANS_CODE:
        qs = qs.filter(**{f"{champ}__isnull": True})
    elif code:
        qs = qs.filter(**{champ: code})
    sections = OrderedDict()
    for l in qs:
        c = l.compte.anal1 if axe == 1 else l.anal2
        cle = c.code if c else SANS_CODE
        s = sections.setdefault(cle, {"code": cle, "libelle": c.libelle if c else "", "comptes": OrderedDict(), "ecritures": []})
        a, b = montants(nature, l.compte_id, l.debit, l.credit)
        cpt = s["comptes"].setdefault(l.compte_id, {"numero": l.compte_id, "libelle": l.compte.libelle, "a": ZERO, "b": ZERO})
        cpt["a"] += a
        cpt["b"] += b
        s["ecritures"].append({"ligne": l, "autre_axe": (l.anal2_id if axe == 1 else (l.compte.anal1_id or "")) or "",
                               "a": a, "b": b})
    res = []
    for s in sections.values():
        s["comptes"] = sorted(s["comptes"].values(), key=lambda x: x["numero"])
        for x in s["comptes"]:
            x["s"] = x["a"] - x["b"]
        s["total"] = _total(s["comptes"])
        res.append(s)
    res.sort(key=lambda s: (s["code"] != SANS_CODE, s["code"]))
    return res


def _contexte(debut, fin, nature):
    n = NATURES[nature]
    return {"debut": debut, "fin": fin, "nature": nature, "natures": NATURES, "titre_nature": n["titre"],
            "col_a": n["colonnes"][0], "col_b": n["colonnes"][1], "col_s": n["colonnes"][2],
            "periode_texte": f"du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"}


@login_required
@consulter
def analytique(request):
    debut, fin = periode(request)
    nature = nature_choisie(request)
    axes = synthese(debut, fin, nature)
    ctx = _contexte(debut, fin, nature)
    if request.GET.get("format") == "xlsx":
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        for a in axes:
            lignes = [[l["code"], l["libelle"], l["a"], l["b"], l["s"]] for l in a["lignes"]]
            t = a["total"]
            lignes.append(["TOTAL", "", t["a"], t["b"], t["s"]])
            feuille(wb, f"Axe {a['axe']}", ["Code", "Libellé", ctx["col_a"], ctx["col_b"], ctx["col_s"]], lignes, (3, 4, 5))
        return reponse_excel(wb, f"Analytique_{nature}_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx")
    return render(request, "compta/analytique.html", {**ctx, "axes": axes})


@login_required
@consulter
def analytique_detail(request):
    debut, fin = periode(request)
    nature = nature_choisie(request)
    axe = 1 if request.GET.get("axe") == "1" else 2
    code = request.GET.get("code") or None
    sections = detail(debut, fin, axe, nature, code)
    ctx = _contexte(debut, fin, nature)
    if request.GET.get("format") == "xlsx":
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        comptes, ecritures = [], []
        for s in sections:
            for x in s["comptes"]:
                comptes.append([s["code"], s["libelle"], x["numero"], x["libelle"], x["a"], x["b"], x["s"]])
            t = s["total"]
            comptes.append([s["code"], "TOTAL " + s["libelle"], "", "", t["a"], t["b"], t["s"]])
            for e in s["ecritures"]:
                l = e["ligne"]
                ecritures.append([s["code"], l.mouvement.date, l.mouvement.numero, l.mouvement.piece, l.mouvement.journal_id,
                                  l.compte_id, l.libelle, e["autre_axe"], e["a"] or None, e["b"] or None])
        feuille(wb, "Par compte", ["Code", "Libellé du code", "Compte", "Libellé du compte", ctx["col_a"], ctx["col_b"],
                                   ctx["col_s"]], comptes, (5, 6, 7))
        ws = feuille(wb, "Écritures", ["Code", "Date", "Mvt", "Pièce", "Journal", "Compte", "Libellé",
                                       "Axe 2" if axe == 1 else "Axe 1", ctx["col_a"], ctx["col_b"]], ecritures, (9, 10))
        for c in ws["B"][1:]:
            c.number_format = "DD/MM/YYYY"
        nom = f"Analytique_{nature}_axe{axe}_{(code or 'tous').replace('/', '-')}_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx"
        return reponse_excel(wb, nom)
    return render(request, "compta/analytique_detail.html", {
        **ctx, "axe": axe, "titre_axe": AXES[axe], "code": code or "", "sections": sections, "sans_code": SANS_CODE,
        "codes": CodeAnalytique.objects.filter(axe=axe).order_by("code"),
        "total": _total([{"a": s["total"]["a"], "b": s["total"]["b"]} for s in sections])})
