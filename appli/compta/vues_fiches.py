"""Fiches bénévoles en ligne : le bénévole note recettes et dépenses, le trésorier complète et reporte."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from . import fiches as moteur
from .forms import AttribuerForm, BenevoleForm, FicheForm, LigneFicheForm
from .models import Fiche, LigneFiche, ModeFiche, Modification, NatureFiche, TiersProvisoire

voir_fiches = permission_required("compta.view_fiche", raise_exception=True)
gerer = permission_required("compta.gerer_fiche", raise_exception=True)


def tresorier(user):
    return user.has_perm("compta.gerer_fiche")


def fiches_visibles(user):
    if tresorier(user) or user.has_perm("compta.view_mouvement"):
        return Fiche.objects.all()
    return Fiche.objects.filter(benevoles=user)


def peut_saisir(fiche, user):
    """Le bénévole saisit tant que la fiche est ouverte ; le trésorier tant qu'elle n'est pas reportée."""
    if tresorier(user):
        return fiche.statut != "reportee"
    return fiche.statut == "ouverte" and user.has_perm("compta.add_lignefiche") and fiche.benevoles.filter(pk=user.pk).exists()


def journaliser(request, action, objet, avant="", apres=""):
    Modification.objects.create(auteur=request.user.get_username(), lot="Fiches", action=action, objet=objet[:200],
                                avant=avant[:300], apres=apres[:300])


@login_required
@voir_fiches
def liste(request):
    fiche_form = benevole_form = None
    if tresorier(request.user):
        fiche_form = FicheForm(request.POST if "creer_fiche" in request.POST else None, prefix="fiche")
        benevole_form = BenevoleForm(request.POST if "creer_benevole" in request.POST else None, prefix="benevole")
        if "creer_fiche" in request.POST and fiche_form.is_valid():
            f = fiche_form.save()
            journaliser(request, "Création", f"fiche {f.pk} {f.titre}", apres=f.get_type_display())
            messages.success(request, f"Fiche créée : {f.titre}.")
            return redirect("fiche", f.pk)
        if "creer_benevole" in request.POST and benevole_form.is_valid():
            c = benevole_form.cleaned_data
            u = User.objects.create_user(c["identifiant"], password=c["mot_de_passe"], first_name=c["prenom"], last_name=c["nom"])
            u.groups.add(Group.objects.get(name="Bénévole"))
            journaliser(request, "Création", f"bénévole {u.username}", apres=u.get_full_name())
            messages.success(request, f"Bénévole créé : {u.get_full_name()} (identifiant {u.username}).")
            return redirect("fiches")
    fiches = fiches_visibles(request.user).prefetch_related("benevoles", "lignes").select_related("anal2")
    return render(request, "compta/fiches.html", {
        "fiches": [(f, moteur.totaux(f)) for f in fiches], "fiche_form": fiche_form, "benevole_form": benevole_form,
        "provisoires": TiersProvisoire.objects.filter(compte__isnull=True).count() if tresorier(request.user) else 0,
    })


def _fiche(request, pk):
    fiche = get_object_or_404(Fiche, pk=pk)
    if not fiches_visibles(request.user).filter(pk=pk).exists():
        raise PermissionDenied
    return fiche


def _parametres_js(fiche):
    return {"natures": {n.pk: n.sens for n in NatureFiche.objects.filter(type_fiche=fiche.type)},
            "modes": {m.pk: m.sens for m in ModeFiche.objects.filter(type_fiche=fiche.type)}}


@login_required
@voir_fiches
def fiche(request, pk):
    fiche = _fiche(request, pk)
    est_tresorier, saisie = tresorier(request.user), peut_saisir(fiche, request.user)
    form = None
    if saisie:
        form = LigneFicheForm(request.POST if "ajouter" in request.POST else None, fiche=fiche, tresorier=est_tresorier,
                              initial={"sens": "R", "date": dt.date.today()})
    if request.method == "POST":
        action = next((a for a in ("ajouter", "transmettre", "rouvrir", "reporter", "modifier") if a in request.POST), None)
        if action == "ajouter" and form and form.is_valid():
            l = form.save(request.user)
            messages.success(request, f"Ligne ajoutée : {l.get_sens_display().lower()} de {l.montant} ₪.")
            return redirect("fiche", fiche.pk)
        if action == "transmettre" and fiche.statut == "ouverte" and saisie:
            fiche.statut = "transmise"
            fiche.save(update_fields=["statut"])
            journaliser(request, "Transmission", f"fiche {fiche.pk} {fiche.titre}")
            messages.success(request, "Fiche transmise au trésorier : elle n'est plus modifiable par les bénévoles.")
            return redirect("fiche", fiche.pk)
        if action == "rouvrir" and est_tresorier and fiche.statut != "ouverte":
            avant = fiche.get_statut_display()
            fiche.statut = "ouverte"
            fiche.save(update_fields=["statut"])
            journaliser(request, "Réouverture", f"fiche {fiche.pk} {fiche.titre}", avant=avant)
            messages.success(request, "Fiche rouverte aux bénévoles (les lignes déjà reportées restent verrouillées).")
            return redirect("fiche", fiche.pk)
        if action == "reporter" and est_tresorier:
            try:
                crees = moteur.reporter(fiche, request.user)
            except ValueError as e:
                messages.error(request, str(e))
            else:
                messages.success(request, f"{len(crees)} mouvement(s) créé(s)" +
                                 (f" : Mvt {crees[0].numero} à {crees[-1].numero}." if crees else "."))
            return redirect("fiche", fiche.pk)
    lignes = [(l, moteur.controler(l)) for l in fiche.lignes.select_related("nature", "mode", "tiers", "provisoire", "mouvement",
                                                                             "compte", "anal2")]
    return render(request, "compta/fiche.html", {
        "fiche": fiche, "form": form, "tresorier": est_tresorier, "saisie": saisie, "totaux": moteur.totaux(fiche),
        "recettes": [x for x in lignes if x[0].sens == "R"], "depenses": [x for x in lignes if x[0].sens == "D"],
        "a_corriger": sum(1 for l, r in lignes if not l.mouvement_id and not r.ok),
        "a_reporter": sum(1 for l, r in lignes if not l.mouvement_id),
        "fiche_form": FicheForm(instance=fiche, prefix="fiche") if est_tresorier else None, "parametres": _parametres_js(fiche),
    })


@login_required
@gerer
def fiche_modifier(request, pk):
    fiche = get_object_or_404(Fiche, pk=pk)
    form = FicheForm(request.POST, instance=fiche, prefix="fiche")
    if form.is_valid():
        form.save()
        journaliser(request, "Modification", f"fiche {fiche.pk} {fiche.titre}",
                    apres=f"axe 2 {fiche.anal2_id or '—'} ; bénévoles {', '.join(u.username for u in fiche.benevoles.all())}")
        messages.success(request, "Fiche mise à jour.")
    else:
        messages.error(request, "Fiche non modifiée : " + "; ".join(f"{k} : {' '.join(v)}" for k, v in form.errors.items()))
    return redirect("fiche", fiche.pk)


@login_required
@voir_fiches
def ligne(request, pk):
    l = get_object_or_404(LigneFiche.objects.select_related("fiche"), pk=pk)
    fiche = _fiche(request, l.fiche_id)
    if l.mouvement_id or not peut_saisir(fiche, request.user):
        raise PermissionDenied
    est_tresorier = tresorier(request.user)
    if "supprimer" in request.POST and request.user.has_perm("compta.delete_lignefiche"):
        journaliser(request, "Suppression", f"ligne de fiche {l.pk} ({fiche.titre})", avant=f"{l.date:%d/%m/%Y} {l.qui} {l.montant}")
        l.delete()
        messages.success(request, "Ligne supprimée.")
        return redirect("fiche", fiche.pk)
    form = LigneFicheForm(request.POST or None, instance=l, fiche=fiche, tresorier=est_tresorier)
    if request.method == "POST" and form.is_valid():
        form.save(request.user)
        messages.success(request, "Ligne modifiée.")
        return redirect("fiche", fiche.pk)
    return render(request, "compta/ligne_fiche.html", {"fiche": fiche, "ligne": l, "form": form, "resultat": moteur.controler(l),
                                                       "parametres": _parametres_js(fiche)})


@login_required
@gerer
def provisoires(request):
    from .membres import creer_tiers
    if request.method == "POST":
        p = get_object_or_404(TiersProvisoire, pk=request.POST.get("provisoire"), compte__isnull=True)
        form = AttribuerForm(request.POST, prefix=f"p{p.pk}")
        if form.is_valid():
            with transaction.atomic():
                compte = form.cleaned_data["compte"]
                if compte is None:
                    compte = creer_tiers(form.cleaned_data["type"], p.nom, p.prenom)
                    journaliser(request, "Création", f"compte {compte.numero}", apres=compte.libelle)
                p.compte = compte
                p.save(update_fields=["compte"])
                journaliser(request, "Tiers provisoire", f"{p.nom} {p.prenom}", apres=f"compte {compte.numero}")
            messages.success(request, f"{p.nom.upper()} {p.prenom.upper()} → compte {compte.numero} – {compte.libelle}.")
            return redirect("provisoires")
    en_attente = [(p, AttribuerForm(prefix=f"p{p.pk}"), p.lignes.count())
                  for p in TiersProvisoire.objects.filter(compte__isnull=True).select_related("cree_par")]
    faits = TiersProvisoire.objects.filter(compte__isnull=False).select_related("compte").order_by("-cree_le")[:30]
    return render(request, "compta/provisoires.html", {"en_attente": en_attente, "faits": faits})
