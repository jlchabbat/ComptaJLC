"""Authentification : un compte par personne, mots de passe hachés, jeton CSRF."""
import os
import secrets
from urllib.parse import urlparse

from flask import (Blueprint, abort, current_app, flash, g, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from .models import Utilisateur, db

bp = Blueprint("auth", __name__)
PUBLIC = {"auth.login", "auth.premier", "static"}

# Trois niveaux d'utilisateur. Les droits sont définis ici, et seulement ici.
ROLES = {"admin": "Administrateur", "gestion": "Gestion (comptabilité)", "benevole": "Bénévole"}
DROITS = {
    "admin": {"consulter", "ecritures", "parametrer", "administrer", "benevoles"},
    "gestion": {"consulter", "ecritures", "benevoles"},
    "benevole": {"benevoles"},   # section bénévoles : à définir plus tard
}
# Droit exigé par page. None = tout utilisateur connecté. Page non listée = « administrer » (refus par défaut).
EXIGE = {
    "compta.accueil": None, "auth.mon_compte": None, "auth.logout": None,
    "compta.benevoles": "benevoles",
    "compta.journal": "consulter", "compta.balance": "consulter", "compta.grand_livre": "consulter",
    "compta.grand_livre_choix": "consulter", "compta.analytique": "consulter", "compta.historique": "consulter",
    "compta.export_journal": "consulter", "compta.export_balance": "consulter",
    "compta.export_historique": "consulter",
    "compta.saisie": "ecritures", "compta.ecriture_modifier": "ecritures",
    "compta.ecriture_supprimer": "ecritures", "compta.ecritures_supprimer": "ecritures",
    "compta.ecritures_importer": "ecritures",
    "compta.plan": "parametrer", "compta.plan_modifier": "parametrer", "compta.plan_supprimer": "parametrer",
    "compta.plan_importer": "parametrer", "compta.axes": "parametrer", "compta.code_ajouter": "parametrer",
    "compta.code_modifier": "parametrer", "compta.code_supprimer": "parametrer",
    "compta.codes_importer": "parametrer", "compta.journaux": "parametrer", "compta.journal_modifier": "parametrer",
    "compta.reinitialiser": "administrer",
    "auth.utilisateurs": "administrer", "auth.supprimer": "administrer", "auth.role": "administrer",
}


def peut(droit):
    u = getattr(g, "utilisateur", None)
    return bool(u and droit in DROITS.get(u.role, ()))
MIN_MDP = 10
# Hachage factice : le temps de réponse ne révèle pas si le nom existe.
FAUX_HASH = generate_password_hash("sans-importance")


def cle_secrete(instance_path):
    """Variable COMPTAJLC_SECRET, sinon clé aléatoire conservée dans instance/ (hors Git)."""
    if os.environ.get("COMPTAJLC_SECRET"):
        return os.environ["COMPTAJLC_SECRET"]
    chemin = os.path.join(instance_path, "secret.key")
    if not os.path.exists(chemin):
        fd = os.open(chemin, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    with open(chemin) as f:
        return f.read().strip()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def garde():
    """Exécutée avant chaque requête : CSRF, puis connexion obligatoire."""
    if request.method == "POST":
        envoye = request.form.get("csrf_token", "")
        if not envoye or not secrets.compare_digest(envoye, session.get("csrf", "")):
            abort(400, "Jeton de sécurité invalide : rechargez la page et recommencez.")
    if request.endpoint in PUBLIC or request.endpoint is None:
        return None
    if Utilisateur.query.first() is None:
        return redirect(url_for("auth.premier"))
    g.utilisateur = db.session.get(Utilisateur, session["uid"]) if "uid" in session else None
    if g.utilisateur is None:
        session.pop("uid", None)
        return redirect(url_for("auth.login", suite=request.full_path.rstrip("?")))
    droit = EXIGE.get(request.endpoint, "administrer")
    if droit and not peut(droit):
        abort(403)
    return None


def mdp_valide(mdp, confirmation):
    if len(mdp) < MIN_MDP:
        return f"Le mot de passe doit comporter au moins {MIN_MDP} caractères."
    if mdp != confirmation:
        return "Les deux mots de passe sont différents."
    return None


def ouvrir_session(u):
    session.clear()
    session["uid"] = u.id
    csrf_token()


@bp.route("/premier-demarrage", methods=["GET", "POST"])
def premier():
    if Utilisateur.query.first() is not None:
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        nom = request.form["nom"].strip()
        erreur = mdp_valide(request.form["mdp"], request.form["mdp2"]) or (None if nom else "Nom obligatoire.")
        if erreur:
            flash(erreur, "erreur")
        else:
            u = Utilisateur(nom=nom, role="admin", mot_de_passe=generate_password_hash(request.form["mdp"]))
            db.session.add(u)
            db.session.commit()
            ouvrir_session(u)
            flash("Compte créé. Vous êtes connecté.", "ok")
            return redirect(url_for("compta.accueil"))
    return render_template("premier.html")


@bp.route("/connexion", methods=["GET", "POST"])
def login():
    if Utilisateur.query.first() is None:
        return redirect(url_for("auth.premier"))
    if request.method == "POST":
        u = Utilisateur.query.filter_by(nom=request.form["nom"].strip()).first()
        ok = check_password_hash(u.mot_de_passe if u else FAUX_HASH, request.form["mdp"])
        if u and ok:
            ouvrir_session(u)
            suite = request.form.get("suite", "")
            # Redirection interne uniquement (pas de lien vers un autre site).
            if suite.startswith("/") and not suite.startswith("//") and not urlparse(suite).netloc:
                return redirect(suite)
            return redirect(url_for("compta.accueil"))
        flash("Nom ou mot de passe incorrect.", "erreur")
    return render_template("login.html", suite=request.args.get("suite", request.form.get("suite", "")))


@bp.post("/deconnexion")
def logout():
    session.clear()
    flash("Vous êtes déconnecté.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/utilisateurs", methods=["GET", "POST"])
def utilisateurs():
    if request.method == "POST":
        nom = request.form["nom"].strip()
        role = request.form.get("role", "")
        erreur = mdp_valide(request.form["mdp"], request.form["mdp2"])
        if not nom:
            erreur = "Nom obligatoire."
        elif role not in ROLES:
            erreur = "Choisissez un niveau d'utilisateur."
        elif Utilisateur.query.filter_by(nom=nom).first():
            erreur = "Ce nom existe déjà."
        if erreur:
            flash(erreur, "erreur")
        else:
            db.session.add(Utilisateur(nom=nom, role=role, mot_de_passe=generate_password_hash(request.form["mdp"])))
            db.session.commit()
            flash("Utilisateur ajouté.", "ok")
        return redirect(url_for("auth.utilisateurs"))
    return render_template("utilisateurs.html", utilisateurs=Utilisateur.query.order_by(Utilisateur.nom).all(),
                           roles=ROLES, droits=DROITS)


@bp.post("/utilisateurs/<int:uid>/role")
def role(uid):
    u = db.get_or_404(Utilisateur, uid)
    nouveau = request.form.get("role", "")
    if nouveau not in ROLES:
        flash("Niveau inconnu.", "erreur")
    elif u.role == "admin" and nouveau != "admin" and Utilisateur.query.filter_by(role="admin").count() <= 1:
        flash("Il doit rester au moins un administrateur.", "erreur")
    else:
        u.role = nouveau
        db.session.commit()
        flash(f"{u.nom} : {ROLES[nouveau]}.", "ok")
    return redirect(url_for("auth.utilisateurs"))


@bp.route("/mon-compte", methods=["GET", "POST"])
def mon_compte():
    u = g.utilisateur
    if request.method == "POST":
        if not check_password_hash(u.mot_de_passe, request.form["ancien"]):
            flash("Ancien mot de passe incorrect.", "erreur")
        else:
            erreur = mdp_valide(request.form["mdp"], request.form["mdp2"])
            if erreur:
                flash(erreur, "erreur")
            else:
                u.mot_de_passe = generate_password_hash(request.form["mdp"])
                db.session.commit()
                flash("Mot de passe modifié.", "ok")
        return redirect(url_for("auth.mon_compte"))
    return render_template("mon_compte.html", roles=ROLES)


@bp.post("/utilisateurs/<int:uid>/supprimer")
def supprimer(uid):
    u = db.get_or_404(Utilisateur, uid)
    if u.id == g.utilisateur.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "erreur")
    else:
        db.session.delete(u)
        db.session.commit()
        flash("Utilisateur supprimé.", "ok")
    return redirect(url_for("auth.utilisateurs"))
