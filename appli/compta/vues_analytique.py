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
AXES = {1: "Nature (axe 1)", 2: "Objet (axe 2 : événement, projet)"}
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
    libelles_autre = dict(CodeAnalytique.objects.filter(axe=2 if axe == 1 else 1).values_list("code", "libelle"))
    sections = OrderedDict()
    for l in qs:
        c = l.compte.anal1 if axe == 1 else l.anal2
        cle = c.code if c else SANS_CODE
        s = sections.setdefault(cle, {"code": cle, "libelle": c.libelle if c else "", "comptes": OrderedDict(), "ecritures": []})
        a, b = montants(nature, l.compte_id, l.debit, l.credit)
        cpt = s["comptes"].setdefault(l.compte_id, {"numero": l.compte_id, "libelle": l.compte.libelle, "a": ZERO, "b": ZERO})
        cpt["a"] += a
        cpt["b"] += b
        autre = (l.anal2_id if axe == 1 else (l.compte.anal1_id or "")) or ""
        s["ecritures"].append({"ligne": l, "autre_axe": autre, "autre_libelle": libelles_autre.get(autre, ""), "a": a, "b": b})
    res = []
    for s in sections.values():
        s["comptes"] = sorted(s["comptes"].values(), key=lambda x: x["numero"])
        for x in s["comptes"]:
            x["s"] = x["a"] - x["b"]
            x["ecritures"] = [e for e in s["ecritures"] if e["ligne"].compte_id == x["numero"]]      # détail par compte
        s["total"] = _total(s["comptes"])
        s["nb_mouvements"] = len({e["ligne"].mouvement_id for e in s["ecritures"]})
        autres = OrderedDict()                                  # répartition par l'autre axe
        for e in s["ecritures"]:
            k = e["autre_axe"] or SANS_CODE
            x = autres.setdefault(k, {"code": k, "libelle": libelles_autre.get(k, ""), "a": ZERO, "b": ZERO})
            x["a"] += e["a"]
            x["b"] += e["b"]
        s["autres"] = sorted(autres.values(), key=lambda x: (x["code"] == SANS_CODE, x["code"]))
        for x in s["autres"]:
            x["s"] = x["a"] - x["b"]
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
    axe = 2 if request.GET.get("axe") == "2" else 1               # une page par axe : Nature (1), Objet (2)
    a = next(x for x in axes if x["axe"] == axe)
    return render(request, "compta/analytique.html", {
        **ctx, "axes": axes, "axe": axe, "a": dict(a, codes=CodeAnalytique.objects.filter(axe=axe).order_by("libelle", "code"))})


def classeur_detail(sections, axe, ctx):
    """État détaillé en Excel : pour chaque code, chiffres clés, répartition par l'autre axe, puis comptes et opérations."""
    import datetime as dt
    from .presentation import Presentation
    a, b, s_ = ctx["col_a"], ctx["col_b"], ctx["col_s"]
    autre = "Axe 2" if axe == 1 else "Axe 1"
    p = Presentation(f"Axe {axe}", "", (11, 8, 9, 44, 16, 16, 16), pied=f"État détaillé {AXES[axe]} · {ctx['periode_texte']}")
    for n, sec in enumerate(sections):
        if n:
            p.ligne += 2
        p.titre(f"État détaillé – {sec['code']}" + (f" – {sec['libelle']}" if sec["libelle"] else ""),
                [f"{AXES[axe]} · {ctx['titre_nature']} · période {ctx['periode_texte']}",
                 f"Édité le {dt.datetime.now():%d/%m/%Y à %H:%M}"])
        t = sec["total"]
        p.section("Chiffres clés")
        p.tableau(["", "", "", "Indicateur", "Montant"], [["", "", "", a, t["a"]], ["", "", "", b, t["b"]], ["", "", "", s_, t["s"]]],
                  montants=(5,))
        p.note(f"{sec['nb_mouvements']} mouvement(s), {len(sec['ecritures'])} ligne(s) d'écriture")
        p.section(f"Répartition par {autre.lower()}")
        p.tableau([autre, "", "", "Libellé", a, b, s_], [[x["code"], "", "", x["libelle"], x["a"], x["b"], x["s"]] for x in sec["autres"]],
                  montants=(5, 6, 7), total=["Total", "", "", "", t["a"], t["b"], t["s"]])
        p.section("Détail par compte")
        for x in sec["comptes"]:
            p.ecrire([f"{x['numero']} – {x['libelle']}"], police=p.police["gras"])
            p.tableau(["Date", "Mvt", "Libellé", "Libellé " + autre.lower(), a, b],
                      [[e["ligne"].mouvement.date, e["ligne"].mouvement.numero, e["ligne"].libelle,
                        e["autre_libelle"] or e["autre_axe"], e["a"] or None, e["b"] or None] for e in x["ecritures"]],
                      montants=(5, 6), formats={1: "DD/MM/YYYY"})
            p.sous_total(["", "", f"Sous-total {x['numero']}", "", x["a"], x["b"]], montants=(5, 6))
        p.ecrire(["Total " + sec["code"], "", "", "", t["a"], t["b"]], police=p.police["gras"], fond=p.fond["total"], montants=(5, 6))
    return p


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
        nom = f"Analytique_{nature}_axe{axe}_{(code or 'tous').replace('/', '-')}_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx"
        return classeur_detail(sections, axe, ctx).reponse(nom)
    return render(request, "compta/analytique_detail.html", {
        **ctx, "axe": axe, "titre_axe": AXES[axe], "code": code or "", "sections": sections, "sans_code": SANS_CODE,
        "codes": CodeAnalytique.objects.filter(axe=axe).order_by("libelle", "code"),
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
