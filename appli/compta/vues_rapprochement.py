"""Banque : import des relevés, puis pour chaque ligne sans écriture, compte de contrepartie et code axe 2 → écriture créée."""


import datetime as dt

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render

from . import echanges
from . import releves as moteur
from .models import CodeAnalytique, Compte, Journal, Ligne, LigneReleve, Modification, ParametreReleve, Traduction

consulter = permission_required("compta.view_lignereleve", raise_exception=True)
pointer = permission_required("compta.pointer_releve", raise_exception=True)


def journaliser(request, action, objet, apres=""):
    Modification.objects.create(auteur=request.user.get_username(), lot="Rapprochement", action=action, objet=objet[:200],
                                apres=apres[:300])


class ImportForm(forms.Form):
    fichier = forms.FileField(label="Relevé (structure Banque : Jnl, Date, Libelle, Debit, Credit, Solde)")



class ParametresForm(forms.ModelForm):
    class Meta:
        model = ParametreReleve
        fields = ["date_reprise", "libelle"]
        widgets = {"date_reprise": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


def journaux():
    return Journal.objects.filter(compte__isnull=False, actif=True)


def _trouver(modele, texte, **filtre):
    """« code – libellé » choisi dans la liste, code seul ou libellé exact."""
    texte = (texte or "").strip()
    if not texte:
        return None
    code = texte.split(" – ")[0].strip()
    qs = modele.objects.filter(**filtre)
    return qs.filter(pk__iexact=code).first() or qs.filter(libelle__iexact=texte).first()


def _affecter(request, journal, lignes):
    """Crée les écritures des lignes affectées ; renvoie (créées, erreurs {pk: message}, saisies {pk: (compte, axe2)})."""
    crees, erreurs, saisies = [], {}, {}
    for l in lignes:
        c, a = request.POST.get(f"compte_{l.pk}", "").strip(), request.POST.get(f"anal2_{l.pk}", "").strip()
        if not c and not a:
            continue
        saisies[l.pk] = (c, a)
        compte = _trouver(Compte, c, actif=True)
        anal2 = _trouver(CodeAnalytique, a, axe=2)
        if not anal2 and not a:
            from .reglages import code_axe2_defaut
            defaut = code_axe2_defaut()                   # un seul axe : code d'office
            anal2 = CodeAnalytique.objects.filter(code=defaut).first() if defaut else None
        if compte and not compte.porte_axe2:
            anal2 = None                                  # axe 2 : comptes 6 et 7 seulement
        elif a and not anal2:
            erreurs[l.pk] = "Code axe 2 introuvable."
            continue
        if not compte or (compte.porte_axe2 and not anal2):
            erreurs[l.pk] = ("Compte introuvable. " if not compte else "Code axe 2 à choisir pour une dépense ou une recette.")
            continue
        try:
            libelle = request.POST.get(f"libelle_{l.pk}", "").strip()
            crees.append(moteur.creer_ecriture(l, compte, anal2, request.user, forcer=bool(request.POST.get(f"nouvelle_{l.pk}")),
                                               libelle=libelle))
            if libelle and request.POST.get(f"lexique_{l.pk}") and Traduction.cle_de(l.operation):
                Traduction.objects.update_or_create(cle=Traduction.cle_de(l.operation)[:120],      # lexique : libellé retenu
                                                    defaults={"hebreu": l.operation[:120], "traduction": libelle[:120]})
        except ValueError as e:
            erreurs[l.pk] = str(e)
        else:
            saisies.pop(l.pk)
    return crees, erreurs, saisies


@login_required
@consulter
def accueil(request, code=None):
    """Relevé téléchargé, lignes sans écriture : affecter compte de contrepartie et code axe 2, puis créer les écritures."""
    js = list(journaux())
    if not js:
        return render(request, "compta/rapprochement.html", {"journaux": []})
    journal = get_object_or_404(Journal, code=code) if code else next(
        (j for j in js if moteur.a_affecter(j).exists()), js[0])
    peut = request.user.has_perm("compta.pointer_releve")
    erreurs, saisies = {}, {}
    if request.method == "POST" and peut:
        if "relier" in request.POST:
            try:
                rel, ecr = request.POST["relier"].split(":")          # « l1,l2…:é1,é2,… » ; « l1,l2,…: » = somme nulle
                ls = [moteur.a_affecter(journal).get(pk=int(x)) for x in rel.split(",")]
                l = ls[0]
                es = [moteur.ecritures(journal).get(pk=int(x), rapprochement__isnull=True) for x in ecr.split(",") if x]
                if es:
                    moteur.pointer(journal, ls, es, request.user, "manuel")
                else:
                    moteur.relier_nulles(ls, request.user)
            except (ValueError, LigneReleve.DoesNotExist, Ligne.DoesNotExist) as err:
                messages.error(request, f"Liaison impossible : ligne ou écriture déjà reliée, ou totaux différents ({err}).")
            else:
                mvts = " + ".join(f"Mvt {e.mouvement.numero}" for e in es) or "elles-mêmes (somme nulle)"
                quoi = f"{len(ls)} lignes du relevé" if len(ls) > 1 else f"Ligne du {l.date:%d/%m/%Y}"
                journaliser(request, "Liaison relevé", f"{journal.code} {l.date:%d/%m/%Y} " + " ; ".join(str(x.montant) for x in ls),
                            apres=mvts)
                messages.success(request, f"{quoi} reliée(s) à {mvts} (aucune écriture créée).")
            return redirect("rapprochement_journal", journal.code)
        if "ecarter_cochees" in request.POST or "ecarter_jusquau" in request.POST:
            qs = moteur.a_affecter(journal)
            if "ecarter_cochees" in request.POST:
                qs = qs.filter(pk__in=[int(x) for x in request.POST.getlist("coche") if x.isdigit()])
            else:
                try:
                    qs = qs.filter(date__lte=dt.date.fromisoformat(request.POST.get("jusquau", "")))
                except ValueError:
                    qs = qs.none()
                    messages.error(request, "Choisir la date jusqu'à laquelle écarter les lignes.")
            n = qs.update(ecartee=True)
            if n:
                journaliser(request, "Lignes de relevé écartées", journal.code, apres=f"{n} ligne(s)")
                messages.success(request, f"{n} ligne(s) écartée(s) : aucune écriture ne sera créée (liste « Lignes écartées »).")
            elif "ecarter_cochees" in request.POST:
                messages.warning(request, "Aucune ligne cochée.")
            return redirect("rapprochement_journal", journal.code)
        if "relier_evidentes" in request.POST:
            n = moteur.relier_evidentes(journal, request.user)
            journaliser(request, "Liaison automatique relevé", journal.code, apres=f"{n} ligne(s) reliée(s)")
            messages.success(request, f"{n} ligne(s) déjà en compta reliée(s) à leur écriture (même montant, une seule écriture possible)."
                             if n else "Aucune ligne n'a une écriture évidente : décider ligne par ligne.")
            return redirect("rapprochement_journal", journal.code)
        if "ecarter" in request.POST or "remettre" in request.POST:
            remettre = "remettre" in request.POST
            qs = moteur.ecartees(journal) if remettre else moteur.a_affecter(journal)
            l = qs.filter(pk=int(request.POST["remettre" if remettre else "ecarter"])).first()
            if l:
                l.ecartee = not remettre
                l.save(update_fields=["ecartee"])
                journaliser(request, "Ligne de relevé " + ("remise" if remettre else "écartée"),
                            f"{journal.code} {l.date:%d/%m/%Y} {l.montant}", apres=l.operation[:200])
                messages.success(request, f"Ligne du {l.date:%d/%m/%Y} ({l.montant}) " +
                                 ("remise dans la liste à affecter." if remettre else "écartée : aucune écriture ne sera créée."))
            return redirect("rapprochement_journal", journal.code)
        crees, erreurs, saisies = _affecter(request, journal, list(moteur.a_affecter(journal)))
        if crees:
            messages.success(request, f"{len(crees)} écriture(s) créée(s) : Mvt " + ", ".join(str(m.numero) for m in crees) + ".")
        if erreurs:
            messages.error(request, f"{len(erreurs)} ligne(s) non enregistrée(s) : voir le motif sur chaque ligne.")
        elif not crees:
            messages.warning(request, "Aucune ligne affectée : choisir un compte et un code axe 2.")
        if not erreurs:
            return redirect("rapprochement_journal", journal.code)
    lignes = []
    memo = moteur.memoire_affectations() if peut else {}
    ctx = moteur.Contexte(journal) if peut else None                  # lu une fois : page rapide même avec beaucoup de lignes
    for l in (ctx.a_affecter if ctx else moteur.a_affecter(journal)):
        c, a = saisies.get(l.pk, ("", ""))
        propose = moteur.proposition(l, memo) if peut and not c else None
        deja = moteur.deja_en_compta(l, ctx) if peut else []
        lignes.append({"l": l, "compte": c, "anal2": a, "libelle": moteur.libelle_releve(l), "erreur": erreurs.get(l.pk, ""), "deja": deja,
                       "propose": f"{propose.numero} – {propose.libelle}" if propose and not deja else "",
                       "groupes": moteur.groupes(l, ctx=ctx) if peut and not deja else [],
                       "lignes_groupees": moteur.lignes_groupees(l, ctx=ctx) if peut and not deja else [],
                       "nulles": moteur.lignes_nulles(l, ctx=ctx) if peut and not deja else None,
                       "pistes": moteur.pistes(l, ctx=ctx) if peut and not deja else None})
    parametres = ParametreReleve.objects.filter(journal=journal).first()
    return render(request, "compta/rapprochement.html", {
        "journaux": js, "journal": journal, "lignes": lignes, "ecartees": list(moteur.ecartees(journal)), "parametres": parametres, "peut": peut, "tolerance": moteur.tolerance(),
        "comptes": Compte.objects.filter(actif=True).exclude(pk=journal.compte_id).order_by("numero") if peut else [],
        "codes": CodeAnalytique.objects.filter(axe=2).exclude(statut=2).order_by("code") if peut else [],
        "a_traduire": sum(1 for x in lignes if x["l"].traduction == "À traduire"),
        "import_form": ImportForm() if peut else None,
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
            texte = echanges.importer_banque(f.name, f.read(), request.user)
        except echanges.Refus as e:
            messages.error(request, "Import refusé : rien n'a été enregistré.")
            for x in e.erreurs[:30]:
                messages.error(request, x)
        else:
            ecarts = len(moteur.ecarts_solde(journal))
            messages.success(request, f"{texte}." + (f" Attention : {ecarts} solde(s) du relevé de {journal.code} incohérent(s)." if ecarts else ""))
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


@login_required
@consulter
def historique(request):
    """Historique des imports de relevés : fichier, banque, date, lignes ajoutées, doublons ignorés."""
    from .models import ImportReleve
    return render(request, "compta/releves_historique.html", {"imports": ImportReleve.objects.select_related("journal")})
