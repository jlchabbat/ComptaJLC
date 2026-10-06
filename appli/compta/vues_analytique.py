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
TITRE = "Anal"
CHAMP = "compte__anal1"
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
    rows = (lignes_periode(debut, fin).filter(filtre_classes(nature))
            .values(CHAMP, f"{CHAMP}__libelle", "compte__numero").annotate(d=Sum("debit"), c=Sum("credit")))
    codes = OrderedDict()
    for r in sorted(rows, key=lambda r: (r[CHAMP] is not None, r[CHAMP] or "")):
        code = r[CHAMP] or SANS_CODE
        x = codes.setdefault(code, {"code": code, "libelle": r[f"{CHAMP}__libelle"] or "", "a": ZERO, "b": ZERO})
        a, b = montants(nature, r["compte__numero"], r["d"] or ZERO, r["c"] or ZERO)
        x["a"] += a
        x["b"] += b
    lignes = list(codes.values())
    for x in lignes:
        x["s"] = x["a"] - x["b"]
    return {"titre": TITRE, "lignes": lignes, "total": _total(lignes)}


def detail(debut, fin, nature, code=None):
    """[{code, libelle, comptes: [{numero, libelle, a, b, s}], ecritures: [...], total}] par code Anal."""
    qs = (lignes_periode(debut, fin).filter(filtre_classes(nature))
          .select_related("mouvement", "compte", "compte__anal1")
          .order_by(CHAMP, "mouvement__date", "mouvement__numero", "ordre"))
    if code == SANS_CODE:
        qs = qs.filter(**{f"{CHAMP}__isnull": True})
    elif code:
        qs = qs.filter(**{CHAMP: code})
    sections = OrderedDict()
    for l in qs:
        c = l.compte.anal1
        cle = c.code if c else SANS_CODE
        s = sections.setdefault(cle, {"code": cle, "libelle": c.libelle if c else "", "comptes": OrderedDict(), "ecritures": []})
        a, b = montants(nature, l.compte_id, l.debit, l.credit)
        cpt = s["comptes"].setdefault(l.compte_id, {"numero": l.compte_id, "libelle": l.compte.libelle, "a": ZERO, "b": ZERO})
        cpt["a"] += a
        cpt["b"] += b
        s["ecritures"].append({"ligne": l, "a": a, "b": b})
    res = []
    for s in sections.values():
        s["comptes"] = sorted(s["comptes"].values(), key=lambda x: x["numero"])
        for x in s["comptes"]:
            x["s"] = x["a"] - x["b"]
            x["ecritures"] = [e for e in s["ecritures"] if e["ligne"].compte_id == x["numero"]]      # détail par compte
        s["total"] = _total(s["comptes"])
        s["nb_mouvements"] = len({e["ligne"].mouvement_id for e in s["ecritures"]})
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
    a = synthese(debut, fin, nature)
    ctx = _contexte(debut, fin, nature)
    if request.GET.get("format") == "xlsx":
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        lignes = [[l["code"], l["libelle"], l["a"], l["b"], l["s"]] for l in a["lignes"]]
        t = a["total"]
        lignes.append(["TOTAL", "", t["a"], t["b"], t["s"]])
        feuille(wb, "Anal", ["Code", "Libellé", ctx["col_a"], ctx["col_b"], ctx["col_s"]], lignes, (3, 4, 5))
        return reponse_excel(wb, f"Analytique_{nature}_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx")
    return render(request, "compta/analytique.html", {
        **ctx, "a": dict(a, codes=CodeAnalytique.objects.order_by("libelle", "code"))})


def classeur_detail(sections, ctx):
    """État détaillé en Excel : pour chaque code Anal, chiffres clés puis comptes et opérations."""
    import datetime as dt
    from .presentation import Presentation
    a, b, s_ = ctx["col_a"], ctx["col_b"], ctx["col_s"]
    p = Presentation("Anal", "", (11, 8, 9, 44, 16, 16, 16), pied=f"État détaillé {TITRE} · {ctx['periode_texte']}")
    for n, sec in enumerate(sections):
        if n:
            p.ligne += 2
        p.titre(f"État détaillé – {sec['code']}" + (f" – {sec['libelle']}" if sec["libelle"] else ""),
                [f"{TITRE} · {ctx['titre_nature']} · période {ctx['periode_texte']}",
                 f"Édité le {dt.datetime.now():%d/%m/%Y à %H:%M}"])
        t = sec["total"]
        p.section("Chiffres clés")
        p.tableau(["", "", "", "Indicateur", "Montant"], [["", "", "", a, t["a"]], ["", "", "", b, t["b"]], ["", "", "", s_, t["s"]]],
                  montants=(5,))
        p.note(f"{sec['nb_mouvements']} mouvement(s), {len(sec['ecritures'])} ligne(s) d'écriture")
        p.section("Détail par compte")
        for x in sec["comptes"]:
            p.ecrire([f"{x['numero']} – {x['libelle']}"], police=p.police["gras"])
            p.tableau(["Date", "Mvt", "Libellé", a, b],
                      [[e["ligne"].mouvement.date, e["ligne"].mouvement.numero, e["ligne"].libelle,
                        e["a"] or None, e["b"] or None] for e in x["ecritures"]],
                      montants=(4, 5), formats={1: "DD/MM/YYYY"})
            p.sous_total(["", "", f"Sous-total {x['numero']}", x["a"], x["b"]], montants=(4, 5))
        p.ecrire(["Total " + sec["code"], "", "", t["a"], t["b"]], police=p.police["gras"], fond=p.fond["total"], montants=(4, 5))
    return p


@login_required
@consulter
def analytique_detail(request):
    debut, fin = periode(request)
    nature = nature_choisie(request)
    code = request.GET.get("code") or None
    sections = detail(debut, fin, nature, code)
    ctx = _contexte(debut, fin, nature)
    if request.GET.get("format") == "xlsx":
        nom = f"Analytique_{nature}_anal_{(code or 'tous').replace('/', '-')}_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx"
        return classeur_detail(sections, ctx).reponse(nom)
    return render(request, "compta/analytique_detail.html", {
        **ctx, "titre_axe": TITRE, "code": code or "", "sections": sections, "sans_code": SANS_CODE,
        "codes": CodeAnalytique.objects.order_by("libelle", "code"),
        "total": _total([{"a": s["total"]["a"], "b": s["total"]["b"]} for s in sections])})


@login_required
@consulter
def axes_comptes(request):
    """Analyse par axes de comptes : axe en lignes, axe en colonnes, filtres, période."""
    from . import axes_comptes as moteur
    debut, fin = periode(request)
    tous = moteur.axes()
    ligne = request.GET.get("lignes") or (tous[3] if len(tous) > 3 else "Axe 1")
    colonne = request.GET.get("colonnes", "")
    mesure = request.GET.get("mesure", "solde") if request.GET.get("mesure") in ("solde", "debit", "credit") else "solde"
    choix = moteur.choix_filtres()
    filtres = {a: request.GET.getlist(f"f_{i}") for i, a in enumerate(choix)}
    t = moteur.analyser(debut, fin, ligne, colonne if colonne != ligne else "", filtres, mesure)
    return render(request, "compta/axes_comptes.html", {
        "debut": debut, "fin": fin, "axes": tous, "ligne": ligne, "colonne": colonne, "mesure": mesure, "t": t,
        "filtres": [(i, a, vals, filtres.get(a, [])) for i, (a, vals) in enumerate(choix.items())]})
