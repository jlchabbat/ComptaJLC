"""Rapports analytiques (Consulter › Analytique) : synthèse par valeur d'un axe et détail d'une valeur ou de toutes
(sous-totaux par compte, écritures), à l'écran, à l'impression et en Excel.

L'axe se choisit : Anal (code du compte, par défaut) ou l'un des axes fixes du plan (une colonne du plan :
RubDecl, Cat, Groupe…, valeurs portées par les comptes). Deux familles de comptes, jamais mélangées :
- gestion (classes 6 et 7) : produit = crédit − débit d'un compte 7, charge = débit − crédit d'un compte 6, résultat ;
- bilan (classes 1 à 5) : débit, crédit et solde (débit − crédit) des mouvements de la période."""

from collections import OrderedDict
from urllib.parse import urlencode

import openpyxl
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Sum
from django.contrib import messages
from django.shortcuts import redirect, render

from .axes_comptes import libelle_propre
from .export import feuille
from .models import ZERO, CodeAnalytique, arrondi
from .views import lignes_periode, periode
from .vues_journaux import reponse_excel

consulter = permission_required("compta.view_mouvement", raise_exception=True)
SANS_CODE = "(sans code)"
TITRE = "Anal"
NATURES = {
    "gestion": {"titre": "Gestion (comptes 6 et 7)", "colonnes": ("Produits", "Charges", "Résultat"), "classes": "67"},
    "bilan": {"titre": "Bilan (comptes 1 à 5)", "colonnes": ("Débit", "Crédit", "Solde"), "classes": "12345"},
}


def axes_proposes():
    """Axes de l'analytique : Anal, puis les axes fixes du plan (Compte et Classe ne sont pas des axes analytiques)."""
    from .axes_comptes import axes
    return [a for a in axes() if a not in ("Compte", "Classe")]


def axe_choisi(request):
    axe = request.GET.get("axe") or TITRE
    return axe if axe in axes_proposes() else TITRE


def codes_des_comptes(axe):
    """{compte: (code, libellé)} sur l'axe ; un compte sans valeur est absent."""
    from .models import Compte, ValeurCompte
    if axe == TITRE:
        return {c.numero: (c.anal1_id, libelle_propre(c.anal1)) for c in Compte.objects.select_related("anal1") if c.anal1_id}
    return {c: (v, "") for c, v in ValeurCompte.objects.filter(axe__nom=axe).values_list("compte_id", "valeur") if v}


def codes_du_choix(axe):
    """[(code, libellé)] de la liste de choix de l'axe."""
    if axe == TITRE:
        return [(x.code, libelle_propre(x)) for x in CodeAnalytique.objects.order_by("libelle", "code")]
    return sorted(set(codes_des_comptes(axe).values()), key=lambda x: (x[1] or x[0]).lower())


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


def codes_choisis(request):
    """Valeurs cochées de l'axe (aucune = toutes)."""
    return [c for c in request.GET.getlist("code") if c]


def synthese(debut, fin, nature, axe=TITRE, choix=None):
    rows = (lignes_periode(debut, fin).filter(filtre_classes(nature))
            .values("compte__numero").annotate(d=Sum("debit"), c=Sum("credit")))
    par_compte = codes_des_comptes(axe)
    codes = OrderedDict()
    for r in sorted(rows, key=lambda r: (r["compte__numero"] in par_compte, par_compte.get(r["compte__numero"], ("",))[0])):
        code, libelle = par_compte.get(r["compte__numero"], (SANS_CODE, ""))
        if choix and code not in choix:
            continue
        x = codes.setdefault(code, {"code": code, "libelle": libelle or "", "a": ZERO, "b": ZERO})
        a, b = montants(nature, r["compte__numero"], r["d"] or ZERO, r["c"] or ZERO)
        x["a"] += a
        x["b"] += b
    lignes = list(codes.values())
    for x in lignes:
        x["s"] = x["a"] - x["b"]
    return {"titre": axe, "lignes": lignes, "total": _total(lignes)}


def detail(debut, fin, nature, code=None, axe=TITRE):
    """[{code, libelle, comptes: [{numero, libelle, a, b, s}], ecritures: [...], total}] par valeur de l'axe ; code : une
    valeur, une liste de valeurs ou rien (toutes)."""
    par_compte = codes_des_comptes(axe)
    choix = [code] if isinstance(code, str) else list(code or [])
    qs = (lignes_periode(debut, fin).filter(filtre_classes(nature))
          .select_related("mouvement", "compte")
          .order_by("mouvement__date", "mouvement__numero", "ordre"))
    if choix:
        q = Q(compte_id__in=[c for c, (v, _) in par_compte.items() if v in choix])
        if SANS_CODE in choix:
            q |= ~Q(compte_id__in=list(par_compte))
        qs = qs.filter(q)
    sections = OrderedDict()
    for l in qs:
        cle, libelle = par_compte.get(l.compte_id, (SANS_CODE, ""))
        s = sections.setdefault(cle, {"code": cle, "libelle": libelle or "", "comptes": OrderedDict(), "ecritures": []})
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


def _contexte(debut, fin, nature, axe=TITRE, choix=()):
    n = NATURES[nature]
    params = urlencode([("axe", axe), ("comptes", nature)] + [("code", c) for c in choix]
                       + [("du", f"{debut:%Y-%m-%d}"), ("au", f"{fin:%Y-%m-%d}")])
    return {"choix": list(choix), "params": params, "sans_code": SANS_CODE, "debut": debut, "fin": fin, "nature": nature, "natures": NATURES, "titre_nature": n["titre"],
            "axe": axe, "axes": axes_proposes(), "codes": codes_du_choix(axe),
            "col_a": n["colonnes"][0], "col_b": n["colonnes"][1], "col_s": n["colonnes"][2],
            "periode_texte": f"du {debut:%d/%m/%Y} au {fin:%d/%m/%Y}"}


@login_required
@consulter
def analytique(request):
    debut, fin = periode(request)
    nature, axe, choix = nature_choisie(request), axe_choisi(request), codes_choisis(request)
    a = synthese(debut, fin, nature, axe, choix)
    ctx = _contexte(debut, fin, nature, axe, choix)
    if request.GET.get("format") == "xlsx":
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        lignes = [[l["code"], l["libelle"], l["a"], l["b"], l["s"]] for l in a["lignes"]]
        t = a["total"]
        lignes.append(["TOTAL", "", t["a"], t["b"], t["s"]])
        feuille(wb, axe[:31], [axe, "Libellé", ctx["col_a"], ctx["col_b"], ctx["col_s"]], lignes, (3, 4, 5))
        return reponse_excel(wb, f"Analytique_{axe}_{nature}_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx")
    return render(request, "compta/analytique.html", {**ctx, "a": a})


def classeur_detail(sections, ctx):
    """État détaillé en Excel : pour chaque valeur de l'axe, chiffres clés puis comptes et opérations."""
    import datetime as dt
    from .presentation import Presentation
    a, b, s_ = ctx["col_a"], ctx["col_b"], ctx["col_s"]
    axe = ctx["axe"]
    p = Presentation(axe[:31], "", (11, 8, 9, 44, 16, 16, 16), pied=f"État détaillé {axe} · {ctx['periode_texte']}")
    for n, sec in enumerate(sections):
        if n:
            p.ligne += 2
        p.titre(f"État détaillé – {sec['code']}" + (f" – {sec['libelle']}" if sec["libelle"] else ""),
                [f"{axe} · {ctx['titre_nature']} · période {ctx['periode_texte']}",
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
    nature, axe, choix = nature_choisie(request), axe_choisi(request), codes_choisis(request)
    sections = detail(debut, fin, nature, choix, axe)
    ctx = _contexte(debut, fin, nature, axe, choix)
    code = choix[0] if len(choix) == 1 else ""
    if request.GET.get("format") == "xlsx":
        quoi = code or (f"{len(choix)}-valeurs" if choix else "tous")
        nom = f"Analytique_{nature}_{axe}_{quoi.replace('/', '-')}_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx"
        return classeur_detail(sections, ctx).reponse(nom)
    return render(request, "compta/analytique_detail.html", {
        **ctx, "titre_axe": axe, "code": code, "sections": sections,
        "total": _total([{"a": s["total"]["a"], "b": s["total"]["b"]} for s in sections])})


@login_required
@consulter
def axes_comptes(request):
    """Tableau croisé dynamique (TCD) : jusqu'à trois champs en lignes, un en colonnes, filtres, valeur, période ;
    ?ecritures=1 liste les écritures d'une case (champs k_<n> = valeur)."""
    from . import tcd
    from .models import Ligne
    if request.method == "POST" and "supprimer_axe" in request.POST:
        return supprimer_axe(request, request.POST["supprimer_axe"])
    debut, fin = periode(request)
    tous = tcd.champs()
    type_comptes = request.GET.get("type") if request.GET.get("type") in tcd.TYPES else "gestion"
    valeur = request.GET.get("valeur") if request.GET.get("valeur") in tcd.VALEURS else (
        "resultat" if type_comptes == "gestion" else "solde")
    lignes = [x for x in (request.GET.get(f"l{i}", "") for i in (1, 2, 3)) if x in tous]
    lignes = list(OrderedDict.fromkeys(lignes)) or ["Anal"]
    colonne = request.GET.get("col", "") if request.GET.get("col", "") in tous and request.GET.get("col") not in lignes else ""
    enrs = tcd.enregistrements(debut, fin, type_comptes)
    choix = tcd.valeurs_des_champs(enrs)
    filtres = {ch: request.GET.getlist(f"f{i}") for i, ch in enumerate(tous)}
    gardes = tcd.filtrer(enrs, filtres)
    if request.GET.get("ecritures"):                       # écritures d'une case du tableau
        criteres = {ch: request.GET[f"k{i}"] for i, ch in enumerate(tous) if f"k{i}" in request.GET}
        cles = {(e["compte"], e["Journal"], e["Mois"]) for e in gardes if all(e[ch] == v for ch, v in criteres.items())}
        q = Q(pk__in=[])
        for compte, journal, mois in cles:
            a, m = map(int, mois.split("-"))
            q |= Q(compte_id=compte, mouvement__journal_id=journal, mouvement__date__year=a, mouvement__date__month=m)
        qs = (Ligne.objects.filter(q, mouvement__date__range=(debut, fin)).select_related("mouvement", "compte")
              .order_by("mouvement__date", "mouvement__numero", "ordre"))
        calcul = tcd.VALEURS[valeur][1]
        lignes_ecr = [(l, calcul(l.debit, l.credit)) for l in qs]
        return render(request, "compta/tcd_ecritures.html", {
            "debut": debut, "fin": fin, "criteres": criteres, "lignes": lignes_ecr, "titre_valeur": tcd.VALEURS[valeur][0],
            "total": sum((m for _, m in lignes_ecr), ZERO), "retour": request.GET.get("retour", "")})
    t = tcd.tableau(gardes, lignes, colonne, valeur)
    if request.GET.get("format") == "xlsx":
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        rangs = [["    " * l["niveau"] + l["libelle"], *l["cellules"], l["total"]] for l in t["lignes"]]
        rangs.append(["Total", *t["totaux"], t["total"]])
        n = len(t["colonnes"])
        feuille(wb, "TCD", [" / ".join(lignes) + (f" × {colonne}" if colonne else ""), *t["colonnes"], "Total"], rangs,
                tuple(range(2, n + 3)))
        return reponse_excel(wb, f"TCD_{'_'.join(lignes)}_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx")
    rang = {ch: i for i, ch in enumerate(tous)}
    for l in t["lignes"]:                                  # lien vers les écritures de la ligne
        l["cles"] = urlencode({f"k{rang[ch]}": v for ch, v in zip(lignes, l["chemin"])})
        l["cases"] = [(m, l["cles"] + "&" + urlencode({f"k{rang[colonne]}": c})) for m, c in zip(l["cellules"], t["colonnes"])]
    return render(request, "compta/axes_comptes.html", {
        "debut": debut, "fin": fin, "champs": tous, "lignes_choisies": lignes + [""] * (3 - len(lignes)), "colonne": colonne,
        "titre_lignes": " › ".join(lignes), "valeur": valeur, "valeurs": tcd.VALEURS, "type": type_comptes, "types": tcd.TYPES,
        "t": t, "axes_plan": [ch for ch in tous[1:] if ch not in tcd.AUTRES],
        "filtres": [(i, ch, choix[ch], filtres.get(ch, [])) for i, ch in enumerate(tous)],
        "nb_filtres": sum(1 for v in filtres.values() if v), "requete": request.GET.urlencode()})


def supprimer_axe(request, nom):
    """Supprime un axe de comptes et ses valeurs (gestion du plan) ; les comptes et les écritures ne changent pas."""
    from .models import AxeCompte, Modification
    if not request.user.has_perm("compta.change_compte"):
        messages.error(request, "Droits insuffisants pour supprimer un axe.")
    else:
        axe = AxeCompte.objects.filter(nom=nom).first()
        if axe:
            n = axe.valeurs.count()
            axe.delete()
            Modification.objects.create(auteur=request.user.get_username(), lot="Plan", action="Suppression d'un axe",
                                        objet=nom[:200], avant=f"{n} valeur(s)")
            messages.success(request, f"Axe « {nom} » supprimé ({n} valeur(s)) ; comptes et écritures inchangés.")
    return redirect("axes_comptes")
