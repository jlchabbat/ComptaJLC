"""Situation financière : le tableau de bord mis en page pour une présentation (bureau, assemblée), en PDF et en Excel."""

import datetime as dt

from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import F, Sum
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
    return classeur(donnees(debut, fin)).reponse(f"Situation_{debut:%Y-%m-%d}_{fin:%Y-%m-%d}.xlsx")


def classeur(d):
    """Situation financière en Excel (A4 portrait, prête à imprimer), même contenu que la page."""
    from .presentation import Presentation
    p = Presentation("Situation", "", (14, 38, 17, 17, 17), pied=f"Situation au {d['fin']:%d/%m/%Y}")
    p.titre("Situation financière" + (f" – {d['association']}" if d["association"] else ""),
            f"Période du {d['debut']:%d/%m/%Y} au {d['fin']:%d/%m/%Y} · éditée le {d['edite_le']:%d/%m/%Y à %H:%M}")
    p.section("Chiffres clés")
    p.tableau(["", "Indicateur", "Montant"],
              [["", "Produits", d["produits"]], ["", "Charges", d["charges"]], ["", "Résultat", d["resultat"]],
               ["", f"Trésorerie au {d['fin']:%d/%m/%Y}", d["total_tresorerie"]]], montants=(3,))
    p.note(f"{d['nb_mouvements']} mouvements sur la période · contrôles : {d['etat']}"
           + (f" ({d['a_verifier']} à vérifier)" if d["a_verifier"] else ""))
    p.section("Trésorerie")
    p.tableau(["Journal", "Compte", "Solde"],
              [[t["journal"].code, f"{t['journal'].compte_id} – {t['journal'].compte.libelle}", t["solde"]] for t in d["tresorerie"]],
              montants=(3,), total=["Total", "", d["total_tresorerie"]])
    for titre, cle in (("Résultat par activité (axe 1)", "axe1"), ("Résultat par événement / projet (axe 2)", "axe2")):
        p.section(titre)
        ls = d[cle]
        p.tableau(["Code", "Libellé", "Produits", "Charges", "Résultat"],
                  [[a["code"] or "(sans code)", a["libelle"] or "", a["produits"], a["charges"], a["resultat"]] for a in ls],
                  montants=(3, 4, 5),
                  total=["Total", "", sum((a["produits"] for a in ls), ZERO), sum((a["charges"] for a in ls), ZERO),
                         sum((a["resultat"] for a in ls), ZERO)])
    for titre, cle, total in (("Produits par compte", "produits_par_compte", d["produits"]),
                              ("Charges par compte", "charges_par_compte", d["charges"])):
        p.section(titre)
        p.tableau(["Compte", "Libellé", "Montant", "Part"],
                  [[c, lib, m, float(m / total) if total else None] for c, lib, m in d[cle]], montants=(3,),
                  total=["Total", "", total, 1 if total else None], formats={4: "0.0 %"})
    return p
