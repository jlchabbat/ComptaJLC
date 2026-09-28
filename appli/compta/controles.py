"""Contrôles de cohérence (cahier des charges §8), repris du classeur."""

from dataclasses import dataclass, field

from django.db.models import Count, F, Q, Sum

from .models import ZERO, arrondi, Compte, Exercice, Ligne, Mouvement, Reglage, soldes


@dataclass
class Resultat:
    regle: str
    libelle: str
    valeur: object
    statut: str                      # OK, Anomalie, À vérifier, Info
    details: list = field(default_factory=list)


def executer():
    res = []
    d, c, _ = soldes(Ligne.objects.all())
    res.append(Resultat("RG-01", "Écart total débit − crédit", d - c, "OK" if d == c else "Anomalie"))

    deseq = (Mouvement.objects.annotate(d=Sum("lignes__debit"), c=Sum("lignes__credit"))
             .exclude(d=F("c")).values_list("numero", "d", "c"))
    deseq = [(n, arrondi(d_), arrondi(c_)) for n, d_, c_ in deseq if arrondi(d_) != arrondi(c_)]
    res.append(Resultat("RG-01", "Mouvements déséquilibrés", len(deseq), "OK" if not deseq else "Anomalie",
                        [f"Mvt {n} : débit {d_} / crédit {c_}" for n, d_, c_ in deseq[:50]]))

    vides = Mouvement.objects.annotate(n=Count("lignes")).filter(n__lt=2).values_list("numero", flat=True)
    res.append(Resultat("RG-01", "Mouvements de moins de 2 lignes", len(vides), "OK" if not vides else "Anomalie",
                        [f"Mvt {n}" for n in vides[:50]]))

    double = Ligne.objects.filter(Q(debit__gt=0, credit__gt=0) | Q(debit=0, credit=0)).count()
    res.append(Resultat("RG-03", "Lignes avec débit ET crédit, ou aucun des deux", double, "OK" if not double else "Anomalie"))

    sans_axe1 = Compte.objects.filter(lignes__isnull=False, anal1__isnull=True).distinct().values_list("numero", flat=True)
    res.append(Resultat("RG-02", "Comptes utilisés sans code d'axe 1", len(sans_axe1), "OK" if not sans_axe1 else "Anomalie",
                        list(sans_axe1)))

    clos = [e for e in Exercice.objects.filter(clos=True)]
    periode_close = Mouvement.objects.none()
    for e in clos:
        periode_close |= Mouvement.objects.filter(date__range=(e.debut, e.fin)).exclude(origine="import")
    n = periode_close.count()
    res.append(Resultat("RG-04", "Écritures nouvelles dans un exercice clos", n, "OK" if not n else "Anomalie",
                        [f"Mvt {m.numero} du {m.date:%d/%m/%Y}" for m in periode_close[:50]]))

    for cle, libelle in (("compte_virement", "Compte de virement interne"), ("compte_attente", "Compte d'attente")):
        numero = Reglage.lire(cle)
        if numero:
            _, _, s = soldes(Ligne.objects.filter(compte_id=numero))
            res.append(Resultat("Liaison", f"{libelle} {numero} : solde", s, "OK" if s == ZERO else "À vérifier"))

    rec = Ligne.objects.filter(compte__numero__startswith="7", debit__gt=0).count()
    dep = Ligne.objects.filter(compte__numero__startswith="6", credit__gt=0).count()
    res.append(Resultat("Info", "Recettes (7xx) au débit : remboursements", rec, "Info"))
    res.append(Resultat("Info", "Dépenses (6xx) au crédit : remboursements", dep, "Info"))
    return res


def etat_general(resultats=None):
    resultats = resultats if resultats is not None else executer()
    anomalies = sum(1 for r in resultats if r.statut == "Anomalie")
    a_verifier = sum(1 for r in resultats if r.statut == "À vérifier")
    return ("OK" if not anomalies else f"{anomalies} anomalie(s)"), a_verifier

