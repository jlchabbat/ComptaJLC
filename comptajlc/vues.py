import csv
import io
import json
import os
import shutil
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template,
                   request, url_for)
from sqlalchemy import func
from werkzeug.security import check_password_hash

from . import imports
from .models import (STATUTS, CodeAxe1, CodeAxe2, Compte, Ecriture, Historique,
                     Journal, Ligne, db)

bp = Blueprint("compta", __name__)


def fmt_montant(c):
    """Centimes -> « 1 234,50 »."""
    s = f"{abs(c or 0) / 100:,.2f}".replace(",", " ").replace(".", ",")
    return ("-" if (c or 0) < 0 else "") + s


def en_centimes(texte):
    texte = (texte or "").strip().replace(" ", "").replace(",", ".")
    if not texte:
        return 0
    try:
        return int((Decimal(texte) * 100).to_integral_value())
    except InvalidOperation:
        raise ValueError(f"Montant invalide : « {texte} »")


@bp.route("/")
def accueil():
    return render_template("accueil.html", nb=Ecriture.query.count())


# ---------- Plan comptable ----------

def axe1_valide(code):
    """'' -> None ; code inconnu -> ValueError."""
    code = (code or "").strip()
    if code and not db.session.get(CodeAxe1, code):
        raise ValueError(f"Code Axe 1 « {code} » inconnu.")
    return code or None


@bp.route("/plan", methods=["GET", "POST"])
def plan():
    if request.method == "POST":
        numero = request.form["numero"].strip()
        libelle = request.form["libelle"].strip()
        try:
            axe1 = axe1_valide(request.form.get("axe1"))
            if not numero.isdigit() or not libelle:
                raise ValueError("Numéro (chiffres) et libellé obligatoires.")
            if db.session.get(Compte, numero):
                raise ValueError("Ce compte existe déjà.")
        except ValueError as e:
            flash(str(e), "erreur")
        else:
            db.session.add(Compte(numero=numero, libelle=libelle, axe1_code=axe1,
                                  lettrable="lettrable" in request.form, actif=True))
            db.session.commit()
            flash("Compte ajouté.", "ok")
        return redirect(url_for("compta.plan"))
    return render_template("plan.html", comptes=Compte.query.order_by(Compte.numero).all(),
                           codes1=CodeAxe1.query.order_by(CodeAxe1.code).all())


@bp.post("/plan/<numero>/modifier")
def plan_modifier(numero):
    c = db.get_or_404(Compte, numero)
    libelle = request.form["libelle"].strip()
    try:
        c.axe1_code = axe1_valide(request.form.get("axe1"))
    except ValueError as e:
        flash(str(e), "erreur")
        return redirect(url_for("compta.plan"))
    if libelle:
        c.libelle = libelle
    c.lettrable = "lettrable" in request.form
    c.actif = "actif" in request.form
    db.session.commit()
    flash(f"Compte {numero} modifié.", "ok")
    return redirect(url_for("compta.plan"))


@bp.post("/plan/<numero>/supprimer")
def plan_supprimer(numero):
    c = db.get_or_404(Compte, numero)
    if Ligne.query.filter_by(compte_numero=numero).first():
        flash("Compte utilisé par des écritures : suppression impossible (décochez « Actif » pour le retirer de la saisie).", "erreur")
    else:
        db.session.delete(c)
        db.session.commit()
        flash("Compte supprimé.", "ok")
    return redirect(url_for("compta.plan"))


def fichier_importe():
    f = request.files.get("fichier")
    if not f or not f.filename:
        raise imports.ErreurImport(["Aucun fichier choisi."])
    return f.read()


def signaler(e):
    flash(f"Import refusé, rien n'a été modifié ({len(e.erreurs)} problème(s)) : " + " | ".join(e.erreurs[:5])
          + (" …" if len(e.erreurs) > 5 else ""), "erreur")


@bp.post("/plan/importer")
def plan_importer():
    """CSV « Compte;Libellé;Axe 1;Lettrable;Actif » : ajoute, met à jour ; tout ou rien."""
    try:
        lignes = imports.lire_plan(fichier_importe(), {c.code for c in CodeAxe1.query})
    except imports.ErreurImport as e:
        signaler(e)
        return redirect(url_for("compta.plan"))
    ajoutes = maj = 0
    for numero, libelle, axe1, lettrable, actif in lignes:
        c = db.session.get(Compte, numero)
        if c:
            maj += 1
        else:
            c = Compte(numero=numero)
            db.session.add(c)
            ajoutes += 1
        c.libelle, c.axe1_code, c.lettrable, c.actif = libelle, axe1, lettrable, actif
    supprimes = 0
    if "remplacer" in request.form:
        dans_fichier = {l[0] for l in lignes}
        for c in Compte.query.all():
            if c.numero not in dans_fichier and not Ligne.query.filter_by(compte_numero=c.numero).first():
                db.session.delete(c)
                supprimes += 1
    db.session.commit()
    flash(f"Plan importé : {ajoutes} ajouté(s), {maj} mis à jour, {supprimes} supprimé(s).", "ok")
    return redirect(url_for("compta.plan"))


# ---------- Codes Axe 1 et Axe 2 ----------

AXES = {1: (CodeAxe1, "Axe 1", "rattaché aux comptes du plan comptable"),
        2: (CodeAxe2, "Axe 2", "activité / projet, choisi à la saisie")}


def modele_axe(n):
    if n not in AXES:
        abort(404)
    return AXES[n][0]


def code_utilise(n, code):
    if n == 1:
        return Compte.query.filter_by(axe1_code=code).first() is not None
    return Ligne.query.filter_by(axe2_code=code).first() is not None


@bp.route("/axes")
def axes():
    return render_template("axes.html", axes=[(n, nom, desc, modele.query.order_by(modele.code).all())
                                              for n, (modele, nom, desc) in AXES.items()], statuts=STATUTS)


@bp.post("/axes/<int:n>/ajouter")
def code_ajouter(n):
    M = modele_axe(n)
    code, libelle = request.form["code"].strip(), request.form["libelle"].strip()
    if not code or not libelle:
        flash("Code et libellé obligatoires.", "erreur")
    elif db.session.get(M, code):
        flash("Ce code existe déjà.", "erreur")
    else:
        db.session.add(M(code=code, libelle=libelle, statut=int(request.form.get("statut", 1))))
        db.session.commit()
        flash("Code ajouté.", "ok")
    return redirect(url_for("compta.axes"))


@bp.post("/axes/<int:n>/<code>/modifier")
def code_modifier(n, code):
    c = db.get_or_404(modele_axe(n), code)
    if request.form["libelle"].strip():
        c.libelle = request.form["libelle"].strip()
    if int(request.form.get("statut", c.statut)) in STATUTS:
        c.statut = int(request.form["statut"])
    db.session.commit()
    flash(f"Code {code} modifié.", "ok")
    return redirect(url_for("compta.axes"))


@bp.post("/axes/<int:n>/<code>/supprimer")
def code_supprimer(n, code):
    c = db.get_or_404(modele_axe(n), code)
    if code_utilise(n, code):
        flash("Code utilisé : suppression impossible (passez-le en « Terminé »).", "erreur")
    else:
        db.session.delete(c)
        db.session.commit()
        flash("Code supprimé.", "ok")
    return redirect(url_for("compta.axes"))


@bp.post("/axes/<int:n>/importer")
def codes_importer(n):
    """CSV « Code;Libellé;Statut » : ajoute, met à jour ; tout ou rien."""
    M = modele_axe(n)
    try:
        lignes = imports.lire_codes(fichier_importe())
    except imports.ErreurImport as e:
        signaler(e)
        return redirect(url_for("compta.axes"))
    ajoutes = maj = supprimes = 0
    for code, libelle, st in lignes:
        c = db.session.get(M, code)
        if c:
            maj += 1
        else:
            c = M(code=code)
            db.session.add(c)
            ajoutes += 1
        c.libelle, c.statut = libelle, st
    if "remplacer" in request.form:
        dans_fichier = {l[0] for l in lignes}
        for c in M.query.all():
            if c.code not in dans_fichier and not code_utilise(n, c.code):
                db.session.delete(c)
                supprimes += 1
    db.session.commit()
    flash(f"{AXES[n][1]} importé : {ajoutes} ajouté(s), {maj} mis à jour, {supprimes} supprimé(s).", "ok")
    return redirect(url_for("compta.axes"))


# ---------- Journaux ----------

@bp.post("/journaux/<code>/modifier")
def journal_modifier(code):
    j = db.get_or_404(Journal, code)
    if request.form["libelle"].strip():
        j.libelle = request.form["libelle"].strip()
        db.session.commit()
        flash("Journal modifié.", "ok")
    return redirect(url_for("compta.journaux"))


@bp.route("/journaux", methods=["GET", "POST"])
def journaux():
    if request.method == "POST":
        code, libelle = request.form["code"].strip().upper(), request.form["libelle"].strip()
        if code and libelle and not db.session.get(Journal, code):
            db.session.add(Journal(code=code, libelle=libelle))
            db.session.commit()
            flash("Journal ajouté.", "ok")
        else:
            flash("Code vide ou déjà utilisé.", "erreur")
        return redirect(url_for("compta.journaux"))
    return render_template("journaux.html", journaux=Journal.query.order_by(Journal.code).all())


# ---------- Saisie, correction, suppression ----------

def instantane(e):
    """Copie lisible d'une écriture (stockée dans l'historique)."""
    return {"date": e.date.isoformat(), "journal": e.journal_code, "piece": e.piece or "",
            "libelle": e.libelle, "lien": e.lien or "",
            "lignes": [{"compte": l.compte_numero, "debit": l.debit, "credit": l.credit,
                        "axe2": l.axe2_code or ""} for l in e.lignes]}


def journaliser(action, mvt, motif, avant, apres):
    db.session.add(Historique(utilisateur=g.utilisateur.nom, action=action, mvt=mvt, motif=motif,
                              avant=json.dumps(avant) if avant else None,
                              apres=json.dumps(apres) if apres else None))


def prochain_mvt():
    """Les numéros de mouvement supprimés ne sont jamais réutilisés (l'historique les cite)."""
    a = db.session.query(func.max(Ecriture.mvt)).scalar() or 0
    b = db.session.query(func.max(Historique.mvt)).scalar() or 0
    return max(a, b) + 1


def centimes_texte(c):
    return f"{c // 100},{c % 100:02d}"


def valeurs_ecriture(e):
    """Valeurs de départ du formulaire pour modifier une écriture."""
    v = {"date": e.date.isoformat(), "journal": e.journal_code, "piece": e.piece or "",
         "libelle": e.libelle, "lien": e.lien or ""}
    for i, l in enumerate(e.lignes):
        v[f"compte{i}"] = l.compte_numero
        v[f"debit{i}"] = centimes_texte(l.debit) if l.debit else ""
        v[f"credit{i}"] = centimes_texte(l.credit) if l.credit else ""
        v[f"axe2_{i}"] = l.axe2_code or ""
    return v


def classes_axe2():
    return tuple(current_app.config["AXE2_CLASSES"])


def lire_formulaire(f, nb_lignes, anciens=None):
    """Valide le formulaire ; lève ValueError (message en français) sinon.

    `anciens` : (comptes, codes axe 2) déjà présents sur l'écriture modifiée, qui restent
    acceptés même si le compte est devenu inactif ou le code terminé.
    """
    comptes_ok, codes_ok = anciens or (set(), set())
    d = datetime.strptime(f["date"], "%Y-%m-%d").date()
    if not f["libelle"].strip():
        raise ValueError("Libellé obligatoire.")
    if not db.session.get(Journal, f["journal"]):
        raise ValueError("Journal inconnu.")
    lignes = []
    for i in range(nb_lignes):
        num = f.get(f"compte{i}", "").strip()
        deb, cre = en_centimes(f.get(f"debit{i}")), en_centimes(f.get(f"credit{i}"))
        axe2 = f.get(f"axe2_{i}", "").strip()
        if not num and not deb and not cre:
            continue
        compte = db.session.get(Compte, num)
        if not compte:
            raise ValueError(f"Ligne {i + 1} : compte « {num} » introuvable.")
        if not compte.actif and num not in comptes_ok:
            raise ValueError(f"Ligne {i + 1} : le compte {num} est inactif.")
        if (deb and cre) or not (deb or cre) or deb < 0 or cre < 0:
            raise ValueError(f"Ligne {i + 1} : un montant positif au débit OU au crédit.")
        if axe2:
            if not num.startswith(classes_axe2()):
                raise ValueError(f"Ligne {i + 1} : l'axe 2 n'est possible que pour les comptes de classe "
                                 + " ou ".join(classes_axe2()) + ".")
            code = db.session.get(CodeAxe2, axe2)
            if not code:
                raise ValueError(f"Ligne {i + 1} : code Axe 2 « {axe2} » inconnu.")
            if code.statut != 1 and axe2 not in codes_ok:
                raise ValueError(f"Ligne {i + 1} : le code Axe 2 {axe2} n'est pas « En cours ».")
        lignes.append((num, deb, cre, axe2 or None))
    if len(lignes) < 2:
        raise ValueError("Au moins deux lignes.")
    if sum(l[1] for l in lignes) != sum(l[2] for l in lignes):
        raise ValueError("Écriture non équilibrée : total débit ≠ total crédit.")
    return d, f["journal"].strip(), f.get("piece", "").strip(), f["libelle"].strip(), lignes, imports.lien_valide(f.get("lien"))


def construire_lignes(lignes):
    return [Ligne(compte_numero=num, debit=deb, credit=cre, axe2_code=axe2) for num, deb, cre, axe2 in lignes]


def contexte_saisie(val, nb_lignes=6, ecriture=None):
    return dict(journaux=Journal.query.all(),
                comptes=Compte.query.filter_by(actif=True).order_by(Compte.numero).all(),
                codes2=CodeAxe2.query.filter_by(statut=1).order_by(CodeAxe2.code).all(),
                classes2=list(classes_axe2()), aujourdhui=date.today().isoformat(),
                nb_lignes=nb_lignes, val=val, ecriture=ecriture)


@bp.route("/saisie", methods=["GET", "POST"])
def saisie():
    ctx = contexte_saisie(request.form if request.method == "POST" else {})
    if request.method == "GET":
        return render_template("saisie.html", **ctx)
    try:
        d, jnl, piece, libelle, lignes, lien = lire_formulaire(request.form, ctx["nb_lignes"])
    except ValueError as e:
        flash(str(e), "erreur")
        return render_template("saisie.html", **ctx), 400
    e = Ecriture(mvt=prochain_mvt(), date=d, journal_code=jnl, piece=piece, libelle=libelle, lien=lien)
    e.lignes = construire_lignes(lignes)
    db.session.add(e)
    db.session.flush()
    journaliser("création", e.mvt, "", None, instantane(e))
    db.session.commit()
    flash(f"Écriture n° {e.mvt} enregistrée.", "ok")
    return redirect(url_for("compta.saisie"))


@bp.route("/ecriture/<int:mvt>/modifier", methods=["GET", "POST"])
def ecriture_modifier(mvt):
    e = db.get_or_404(Ecriture, mvt)
    nb = max(6, len(e.lignes) + 2)
    post = request.method == "POST"
    ctx = contexte_saisie(request.form if post else valeurs_ecriture(e), nb, ecriture=e)
    ctx["comptes"] = Compte.query.filter((Compte.actif == True) | Compte.numero.in_(  # noqa: E712
        {l.compte_numero for l in e.lignes})).order_by(Compte.numero).all()
    anciens2 = {l.axe2_code for l in e.lignes if l.axe2_code}
    ctx["codes2"] = CodeAxe2.query.filter((CodeAxe2.statut == 1) | CodeAxe2.code.in_(anciens2)).order_by(CodeAxe2.code).all()
    if not post:
        return render_template("saisie.html", **ctx)
    try:
        motif = request.form.get("motif", "").strip()
        if not motif:
            raise ValueError("Indiquez le motif de la modification.")
        d, jnl, piece, libelle, lignes, lien = lire_formulaire(request.form, nb, ({l.compte_numero for l in e.lignes}, {l.axe2_code for l in e.lignes if l.axe2_code}))
    except ValueError as err:
        flash(str(err), "erreur")
        return render_template("saisie.html", **ctx), 400
    avant = instantane(e)
    e.date, e.journal_code, e.piece, e.libelle, e.lien = d, jnl, piece, libelle, lien
    e.lignes = construire_lignes(lignes)
    db.session.flush()
    db.session.refresh(e)
    journaliser("modification", mvt, motif, avant, instantane(e))
    db.session.commit()
    flash(f"Écriture n° {mvt} modifiée.", "ok")
    return redirect(url_for("compta.journal"))


@bp.post("/ecriture/<int:mvt>/supprimer")
def ecriture_supprimer(mvt):
    e = db.get_or_404(Ecriture, mvt)
    motif = request.form.get("motif", "").strip()
    if not motif:
        flash("Indiquez le motif de la suppression.", "erreur")
        return redirect(url_for("compta.ecriture_modifier", mvt=mvt))
    journaliser("suppression", mvt, motif, instantane(e), None)
    db.session.delete(e)
    db.session.commit()
    flash(f"Écriture n° {mvt} supprimée (conservée dans l'historique).", "ok")
    return redirect(url_for("compta.journal"))


@bp.post("/ecritures/importer")
def ecritures_importer():
    """CSV d'écritures (voir docs/import-ecritures.md) : tout ou rien, numéros de mouvement conservés."""
    renum = "renumeroter" in request.form
    try:
        octets = fichier_importe()
        res = imports.lire_ecritures(
            octets, {c.numero: c.axe1_code for c in Compte.query},
            {c.code for c in CodeAxe1.query}, {c.code for c in CodeAxe2.query}, classes_axe2(),
            {m for (m,) in db.session.query(Ecriture.mvt)} | {m for (m,) in db.session.query(Historique.mvt)},
            renumeroter=renum, premier_numero=prochain_mvt())
    except imports.ErreurImport as e:
        signaler(e)
        return redirect(url_for("compta.journal"))
    nom = request.files["fichier"].filename
    for code in sorted(res["journaux"]):
        if not db.session.get(Journal, code):
            db.session.add(Journal(code=code, libelle=code))
    for num, (lib, axe1) in res["comptes_a_creer"].items():
        db.session.add(Compte(numero=num, libelle=lib, axe1_code=axe1))
    db.session.flush()
    nb_lignes = 0
    for m in res["mouvements"]:
        e = Ecriture(mvt=m["mvt"], date=m["date"], journal_code=m["journal"], libelle=m["libelle"],
                     lien=m["lien"], piece="")
        e.lignes = construire_lignes(m["lignes"])
        nb_lignes += len(e.lignes)
        db.session.add(e)
        db.session.flush()
        db.session.refresh(e)
        journaliser("création", e.mvt, f"Import CSV : {nom}" + (f" (n° {m['ancien']} dans le fichier)" if renum else ""),
                    None, instantane(e))
    db.session.commit()
    plage = (f" renumérotées {res['mouvements'][0]['mvt']} à {res['mouvements'][-1]['mvt']}"
             if renum and res["mouvements"] else "")
    flash(f"Import réussi : {len(res['mouvements'])} écritures{plage} ({nb_lignes} lignes), "
          f"{len(res['comptes_a_creer'])} compte(s) créé(s), "
          f"{res['ignores_axe2']} code(s) Axe 2 ignoré(s) sur des comptes hors classes "
          + " et ".join(classes_axe2()) + ".", "ok")
    return redirect(url_for("compta.journal"))


PHRASE_VIDER = "VIDER"


def sauvegarder_base():
    """Copie du fichier SQLite dans instance/sauvegardes/ ; None si la base n'est pas un fichier."""
    chemin = db.engine.url.database
    if not chemin or not os.path.exists(chemin):
        return None
    dossier = os.path.join(current_app.instance_path, "sauvegardes")
    os.makedirs(dossier, exist_ok=True)
    dest = os.path.join(dossier, "compta-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".db")
    shutil.copy2(chemin, dest)
    return os.path.basename(dest)


@bp.route("/reinitialiser", methods=["GET", "POST"])
def reinitialiser():
    """Vide l'application pour la recharger par les imports CSV (copie de sauvegarde faite avant)."""
    if request.method == "POST":
        portee = request.form.get("portee")
        if portee not in ("ecritures", "tout"):
            flash("Choisissez ce qu'il faut vider.", "erreur")
        elif request.form.get("phrase", "").strip() != PHRASE_VIDER:
            flash(f"Tapez {PHRASE_VIDER} en majuscules pour confirmer.", "erreur")
        elif not check_password_hash(g.utilisateur.mot_de_passe, request.form.get("mdp", "")):
            flash("Mot de passe incorrect.", "erreur")
        else:
            copie = sauvegarder_base()
            nb = Ecriture.query.count()
            Ligne.query.delete()
            Ecriture.query.delete()
            if portee == "tout":
                Compte.query.delete()
                CodeAxe2.query.delete()
                CodeAxe1.query.delete()
            # L'historique est vidé avec les écritures (sinon les numéros de mouvement resteraient
            # « pris » et le rechargement serait refusé) ; la copie de sauvegarde le conserve.
            Historique.query.delete()
            journaliser("réinitialisation", 0,
                        ("Écritures" if portee == "ecritures" else "Écritures, plan comptable, codes Axe 1 et Axe 2")
                        + f" supprimés ({nb} écritures)" + (f" ; copie : {copie}" if copie else ""), None, None)
            db.session.commit()
            flash(f"Application vidée ({nb} écritures supprimées)."
                  + (f" Copie de sauvegarde : instance/sauvegardes/{copie}." if copie else "")
                  + " Vous pouvez recharger vos fichiers CSV.", "ok")
            return redirect(url_for("compta.accueil"))
    return render_template("reinitialiser.html", nb=Ecriture.query.count(), nb_comptes=Compte.query.count(),
                           nb1=CodeAxe1.query.count(), nb2=CodeAxe2.query.count(), phrase=PHRASE_VIDER)


@bp.route("/export/historique.xlsx")
def export_historique():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Historique"
    for k, h in enumerate(["Date", "Utilisateur", "Action", "Mvt", "Motif", "Avant", "Après"], 1):
        _texte(ws, 1, k, h)
    for r, h in enumerate(Historique.query.order_by(Historique.id).all(), 2):
        ws.cell(row=r, column=1, value=h.quand).number_format = "DD/MM/YYYY HH:MM"
        _texte(ws, r, 2, h.utilisateur)
        _texte(ws, r, 3, h.action)
        ws.cell(row=r, column=4, value=h.mvt)
        _texte(ws, r, 5, h.motif or "")
        _texte(ws, r, 6, resume_ecriture(json.loads(h.avant)) if h.avant else "")
        _texte(ws, r, 7, resume_ecriture(json.loads(h.apres)) if h.apres else "")
    return _reponse(wb, "historique.xlsx")


@bp.route("/historique")
def historique():
    rows = Historique.query.order_by(Historique.id.desc()).all()
    return render_template("historique.html", rows=[(h, json.loads(h.avant) if h.avant else None,
                                                     json.loads(h.apres) if h.apres else None) for h in rows])


@bp.app_template_filter("resume_ecriture")
def resume_ecriture(snap):
    if not snap:
        return ""
    out = [f"{snap['date']} · {snap['journal']} · {snap['piece']} · {snap['libelle']}"]
    for l in snap["lignes"]:
        sens = f"D {fmt_montant(l['debit'])}" if l["debit"] else f"C {fmt_montant(l['credit'])}"
        ext = l.get("axe2") or " ; ".join(l.get("analytique", []))
        ana = f" [{ext}]" if ext else ""
        out.append(f"  {l['compte']}  {sens}{ana}")
    return "\n".join(out)


# ---------- États ----------

PAR_PAGE = 50
FILTRES = ("q", "journal", "compte", "axe2", "du", "au", "mvt_de", "mvt_a")


def echapper_like(t):
    return t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def ecritures_filtrees(args):
    """Requête des écritures selon les filtres de la page Journal (champs vides ignorés)."""
    q = Ecriture.query
    if args.get("q", "").strip():
        t = "%" + echapper_like(args["q"].strip()) + "%"
        q = q.filter(Ecriture.libelle.ilike(t, escape="\\") | Ecriture.piece.ilike(t, escape="\\"))
    if args.get("journal"):
        q = q.filter(Ecriture.journal_code == args["journal"])
    if args.get("compte", "").strip():
        q = q.filter(Ecriture.lignes.any(Ligne.compte_numero.like(echapper_like(args["compte"].strip()) + "%", escape="\\")))
    if args.get("axe2"):
        q = q.filter(Ecriture.lignes.any(Ligne.axe2_code == args["axe2"]))
    for cle, champ, op in (("du", Ecriture.date, ">="), ("au", Ecriture.date, "<=")):
        if args.get(cle):
            try:
                d = datetime.strptime(args[cle], "%Y-%m-%d").date()
            except ValueError:
                continue
            q = q.filter(champ >= d if op == ">=" else champ <= d)
    for cle, op in (("mvt_de", ">="), ("mvt_a", "<=")):
        if args.get(cle, "").strip().isdigit():
            n = int(args[cle])
            q = q.filter(Ecriture.mvt >= n if op == ">=" else Ecriture.mvt <= n)
    return q.order_by(Ecriture.date, Ecriture.mvt)


@bp.route("/journal")
def journal():
    q = ecritures_filtrees(request.args)
    total = q.count()
    pages = max(1, -(-total // PAR_PAGE))
    page = min(max(request.args.get("page", 1, type=int), 1), pages)
    ecritures = q.limit(PAR_PAGE).offset((page - 1) * PAR_PAGE).all()
    mvts = q.with_entities(Ecriture.mvt).subquery()
    somme = db.session.query(func.sum(Ligne.debit)).filter(Ligne.mvt.in_(db.select(mvts.c.mvt))).scalar() or 0
    filtres = {k: request.args[k] for k in FILTRES if request.args.get(k)}
    return render_template("journal.html", ecritures=ecritures, total=total, page=page, pages=pages,
                           somme=somme, filtres=filtres, journaux=Journal.query.order_by(Journal.code).all(),
                           codes2=CodeAxe2.query.order_by(CodeAxe2.code).all(), par_page=PAR_PAGE)


@bp.post("/ecritures/supprimer")
def ecritures_supprimer():
    """Suppression de plusieurs écritures cochées : motif obligatoire, une trace par écriture."""
    mvts = request.form.getlist("mvt", type=int)
    motif = request.form.get("motif", "").strip()
    retour = request.form.get("retour", "")
    retour = retour if retour.startswith("?") else ""
    if not mvts:
        flash("Aucune écriture cochée.", "erreur")
    elif not motif:
        flash("Indiquez le motif de la suppression.", "erreur")
    else:
        n = 0
        for e in Ecriture.query.filter(Ecriture.mvt.in_(mvts)).all():
            journaliser("suppression", e.mvt, motif, instantane(e), None)
            db.session.delete(e)
            n += 1
        db.session.commit()
        flash(f"{n} écriture(s) supprimée(s) (conservées dans l'historique).", "ok")
    return redirect(url_for("compta.journal") + retour)


def lignes_balance():
    return (db.session.query(Ligne.compte_numero, Compte.libelle, func.sum(Ligne.debit),
                             func.sum(Ligne.credit), Compte.axe1_code)
            .join(Compte).group_by(Ligne.compte_numero).order_by(Ligne.compte_numero).all())


@bp.route("/balance")
def balance():
    rows = lignes_balance()
    return render_template("balance.html", rows=rows,
                           td=sum(r[2] for r in rows), tc=sum(r[3] for r in rows))


@bp.route("/grand-livre/<numero>")
def grand_livre(numero):
    c = db.get_or_404(Compte, numero)
    lignes = (Ligne.query.filter_by(compte_numero=numero).join(Ecriture)
              .order_by(Ecriture.date, Ecriture.mvt).all())
    return render_template("grand_livre.html", compte=c, lignes=lignes)


@bp.route("/analytique/<int:n>")
def analytique(n):
    M = modele_axe(n)
    q = db.session.query(M.code, M.libelle, func.sum(Ligne.debit), func.sum(Ligne.credit))
    if n == 1:
        q = q.join(Compte, Compte.axe1_code == M.code).join(Ligne, Ligne.compte_numero == Compte.numero)
    else:
        q = q.join(Ligne, Ligne.axe2_code == M.code)
    return render_template("analytique.html", nom=AXES[n][1], rows=q.group_by(M.code).order_by(M.code).all())


# ---------- Exports Excel ----------

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _texte(ws, ligne, col, valeur):
    """Écrit un texte sans jamais l'interpréter comme une formule (=, +, -, @)."""
    c = ws.cell(row=ligne, column=col, value=valeur)
    if isinstance(valeur, str):
        c.data_type = "s"
    return c


def _reponse(wb, nom):
    from openpyxl.styles import Font
    for ws in wb.worksheets:
        for c in ws[1]:
            c.font = Font(bold=True)
        ws.freeze_panes = "A2"
        for col in ws.columns:
            ws.column_dimensions[col[0].column_letter].width = min(
                50, max(10, max(len(str(c.value or "")) for c in col) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return Response(buf.getvalue(), mimetype=XLSX,
                    headers={"Content-Disposition": f"attachment; filename={nom}"})


@bp.route("/export/journal.xlsx")
def export_journal():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Journal"
    for k, h in enumerate(["Mvt", "Date", "Journal", "Pièce", "Libellé", "Compte", "Libellé du compte",
                           "Débit", "Crédit", "Axe 1", "Axe 2", "Lien"], 1):
        _texte(ws, 1, k, h)
    r = 2
    for e in ecritures_filtrees(request.args).all():
        for l in e.lignes:
            ws.cell(row=r, column=1, value=e.mvt)
            ws.cell(row=r, column=2, value=e.date).number_format = "DD/MM/YYYY"
            _texte(ws, r, 3, e.journal_code)
            _texte(ws, r, 4, e.piece or "")
            _texte(ws, r, 5, e.libelle)
            _texte(ws, r, 6, l.compte_numero)
            _texte(ws, r, 7, l.compte.libelle)
            ws.cell(row=r, column=8, value=l.debit / 100 if l.debit else None).number_format = "#,##0.00"
            ws.cell(row=r, column=9, value=l.credit / 100 if l.credit else None).number_format = "#,##0.00"
            if l.compte.axe1:
                _texte(ws, r, 10, f"{l.compte.axe1.code} {l.compte.axe1.libelle}")
            if l.axe2:
                _texte(ws, r, 11, f"{l.axe2.code} {l.axe2.libelle}")
            _texte(ws, r, 12, e.lien or "")
            r += 1
    return _reponse(wb, "journal.xlsx")


@bp.route("/export/balance.xlsx")
def export_balance():
    from openpyxl import Workbook
    rows = lignes_balance()
    wb = Workbook()
    ws = wb.active
    ws.title = "Balance"
    for k, h in enumerate(["Compte", "Libellé", "Débit", "Crédit", "Solde", "Axe 1"], 1):
        _texte(ws, 1, k, h)
    for r, (n, lib, d, c, axe1) in enumerate(rows, 2):
        _texte(ws, r, 1, n)
        _texte(ws, r, 2, lib)
        ws.cell(row=r, column=3, value=d / 100).number_format = "#,##0.00"
        ws.cell(row=r, column=4, value=c / 100).number_format = "#,##0.00"
        ws.cell(row=r, column=5, value=f"=C{r}-D{r}").number_format = "#,##0.00"
        _texte(ws, r, 6, axe1 or "")
    t = len(rows) + 2
    _texte(ws, t, 2, "Total")
    for col, L in ((3, "C"), (4, "D"), (5, "E")):
        ws.cell(row=t, column=col, value=f"=SUM({L}2:{L}{t - 1})").number_format = "#,##0.00"
    return _reponse(wb, "balance.xlsx")
