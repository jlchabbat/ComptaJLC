"""Rapprochement bancaire : import des relevés, pointage automatique et manuel, état de rapprochement."""

import datetime as dt
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from . import releves as moteur
from .models import Journal, Ligne, LigneReleve, Modification, MoyenPaiement, ParametreReleve, Rapprochement, Traduction

consulter = permission_required("compta.view_lignereleve", raise_exception=True)
pointer = permission_required("compta.pointer_releve", raise_exception=True)


def journaliser(request, action, objet, apres=""):
    Modification.objects.create(auteur=request.user.get_username(), lot="Rapprochement", action=action, objet=objet[:200],
                                apres=apres[:300])


class ImportForm(forms.Form):
    fichier = forms.FileField(label="Relevé (PDF, Excel ou CSV)")
    solde_ouverture = forms.DecimalField(required=False, max_digits=14, decimal_places=2, label="Solde d'ouverture",
                                         help_text="Seulement au premier import du compte, si le relevé n'indique pas les soldes.")


class ParametresForm(forms.ModelForm):
    class Meta:
        model = ParametreReleve
        fields = ["date_reprise", "libelle"]
        widgets = {"date_reprise": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


def journaux():
    return Journal.objects.filter(compte__isnull=False, actif=True)


@login_required
@consulter
def accueil(request, code=None):
    js = list(journaux())
    if not js:
        return render(request, "compta/rapprochement.html", {"journaux": []})
    journal = get_object_or_404(Journal, code=code) if code else next(
        (j for j in js if LigneReleve.objects.filter(journal=j).exists()), js[0])
    derniere = LigneReleve.objects.filter(journal=journal).order_by("-date").first()
    try:
        jusquau = dt.date.fromisoformat(request.GET["au"])
    except (KeyError, ValueError):
        jusquau = derniere.date if derniere else dt.date.today()
    peut = request.user.has_perm("compta.pointer_releve")
    parametres = ParametreReleve.objects.filter(journal=journal).first()
    return render(request, "compta/rapprochement.html", {
        "journaux": js, "journal": journal, "etat": moteur.etat(journal, jusquau), "mois": moteur.par_mois(journal),
        "nb_releve": LigneReleve.objects.filter(journal=journal, ouverture=False).count(),
        "ecarts_solde": moteur.ecarts_solde(journal), "parametres": parametres, "tolerance": moteur.tolerance(),
        "a_traduire": sum(1 for l in LigneReleve.objects.filter(journal=journal, ouverture=False) if l.traduction == "À traduire"),
        "peut": peut, "import_form": ImportForm() if peut else None,
        "parametres_form": (ParametresForm(instance=parametres or ParametreReleve(journal=journal))
                            if request.user.has_perm("compta.parametrer") else None),
    })


@login_required
@pointer
def importer(request, code):
    journal = get_object_or_404(Journal, code=code)
    form = ImportForm(request.POST, request.FILES)
    if form.is_valid():
        f = form.cleaned_data["fichier"]
        try:
            lignes = moteur.lire(f.name, f.read())
            if not lignes:
                raise ValueError("Aucune ligne de mouvement reconnue (en-têtes Date, Montant ou Crédit / Débit attendus).")
            ajoutees, doublons, ecarts = moteur.importer(journal, lignes, source=f.name,
                                                         solde_ouverture=form.cleaned_data["solde_ouverture"])
        except ValueError as e:
            messages.error(request, f"Import refusé : {e}")
        else:
            journaliser(request, "Import relevé", f"{journal.code} {f.name}", apres=f"{ajoutees} lignes, {doublons} déjà présentes")
            messages.success(request, f"{ajoutees} ligne(s) ajoutée(s), {doublons} déjà présente(s) ignorée(s)."
                             + (f" Attention : {ecarts} solde(s) du relevé incohérent(s)." if ecarts else ""))
    else:
        messages.error(request, "Choisir un fichier.")
    return redirect("rapprochement_journal", journal.code)


@login_required
@permission_required("compta.parametrer", raise_exception=True)
def parametres(request, code):
    journal = get_object_or_404(Journal, code=code)
    instance = ParametreReleve.objects.filter(journal=journal).first() or ParametreReleve(journal=journal)
    form = ParametresForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        journaliser(request, "Paramètres relevé", journal.code, apres=f"reprise {instance.date_reprise}")
        messages.success(request, "Paramètres enregistrés.")
    return redirect("rapprochement_journal", journal.code)


@login_required
@pointer
def automatique(request, code):
    journal = get_object_or_404(Journal, code=code)
    n = moteur.automatique(journal, request.user)
    journaliser(request, "Pointage automatique", journal.code, apres=f"{n} rapprochement(s)")
    messages.success(request, f"{n} rapprochement(s) automatique(s) (même montant, ± {moteur.tolerance()} jours).")
    return redirect("pointage", journal.code)


@login_required
@consulter
def pointage(request, code):
    journal = get_object_or_404(Journal, code=code)
    peut = request.user.has_perm("compta.pointer_releve")
    if request.method == "POST" and peut:
        if "depointer" in request.POST:
            r = get_object_or_404(Rapprochement, pk=request.POST["depointer"], journal=journal)
            journaliser(request, "Dépointage", f"{journal.code} R{r.pk}")
            moteur.depointer(r)
            messages.success(request, f"Rapprochement R{r.pk} annulé.")
        else:
            try:
                with transaction.atomic():
                    r = moteur.pointer(journal, LigneReleve.objects.filter(journal=journal, pk__in=request.POST.getlist("releve")),
                                       moteur.ecritures(journal).filter(pk__in=request.POST.getlist("ecriture")), request.user)
            except ValueError as e:
                messages.error(request, str(e))
            else:
                journaliser(request, "Pointage manuel", f"{journal.code} R{r.pk}")
                messages.success(request, f"Pointé : R{r.pk}.")
        return redirect("pointage", journal.code)
    releve = LigneReleve.objects.filter(journal=journal, rapprochement__isnull=True)
    ecr = moteur.ecritures(journal).filter(rapprochement__isnull=True).order_by("mouvement__date", "mouvement__numero")
    faits = (Rapprochement.objects.filter(journal=journal).prefetch_related("releves", "ecritures__mouvement")[:200])
    return render(request, "compta/pointage.html", {"journal": journal, "releve": releve, "ecritures": ecr, "faits": faits,
                                                     "peut": peut, "tolerance": moteur.tolerance()})


@login_required
@pointer
def creer_ecriture(request, pk):
    """Ouvre la saisie pré-remplie depuis une ligne du relevé non pointée."""
    l = get_object_or_404(LigneReleve, pk=pk, rapprochement__isnull=True)
    mp = MoyenPaiement.objects.filter(journal=l.journal).first()
    params = {"date": l.date.isoformat(), "montant": abs(l.montant), "releve": l.pk,
              "libelle": (l.traduction if l.traduction != "À traduire" else "")[:60].upper()}
    if mp:
        params["paiement"] = mp.pk
    return redirect(reverse("saisie") + "?" + urlencode(params))


def pointer_apres_saisie(releve_id, mouvements, utilisateur):
    """Après une saisie lancée depuis le relevé : pointe l'écriture de banque de même montant."""
    l = LigneReleve.objects.filter(pk=releve_id, rapprochement__isnull=True).first()
    if not l:
        return None
    e = Ligne.objects.filter(mouvement__in=mouvements, compte=l.journal.compte, rapprochement__isnull=True).filter(
        debit=l.montant if l.montant > 0 else 0, credit=-l.montant if l.montant < 0 else 0).first()
    return moteur.pointer(l.journal, [l], [e], utilisateur, "saisie") if e else None


@login_required
@pointer
def traductions(request):
    if request.method == "POST":
        n = 0
        for cle, valeur in request.POST.items():
            if cle.startswith("t_") and valeur.strip():
                hebreu = request.POST.get("h_" + cle[2:], "")
                Traduction.objects.update_or_create(cle=Traduction.cle_de(hebreu)[:120],
                                                    defaults={"hebreu": hebreu[:120], "traduction": valeur.strip()[:120]})
                n += 1
        if n:
            journaliser(request, "Traductions", f"{n} opération(s)")
        messages.success(request, f"{n} traduction(s) enregistrée(s).")
        return redirect("traductions")
    vus, a_traduire = set(), []
    for l in LigneReleve.objects.filter(ouverture=False).order_by("-date"):
        cle = Traduction.cle_de(l.operation)
        if cle and cle not in vus and l.traduction == "À traduire":
            vus.add(cle)
            a_traduire.append(l)
    return render(request, "compta/traductions.html", {"a_traduire": a_traduire, "connues": Traduction.objects.all()})
