import os

from flask import Flask

from . import auth
from .models import db


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=auth.cle_secrete(app.instance_path),
        AXE2_CLASSES="67",  # classes de comptes pouvant recevoir un code Axe 2
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not app.debug and not os.environ.get("COMPTAJLC_HTTP"),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(app.instance_path, "compta.db"),
    )
    if config:
        app.config.update(config)
    db.init_app(app)

    from . import vues
    app.register_blueprint(auth.bp)
    app.register_blueprint(vues.bp)
    app.before_request(auth.garde)
    app.jinja_env.globals["csrf_token"] = auth.csrf_token
    app.jinja_env.globals["peut"] = auth.peut
    app.jinja_env.globals["ROLES"] = auth.ROLES

    messages = {400: "Requête refusée (jeton de sécurité périmé ?). Rechargez la page et recommencez.",
                403: "Droits insuffisants : cette page n'est pas accessible avec votre niveau d'utilisateur.",
                404: "Page introuvable."}

    def erreur(e):
        from flask import render_template
        return render_template("erreur.html", code=e.code, message=messages.get(e.code, e.description)), e.code
    for code in messages:
        app.register_error_handler(code, erreur)
    app.jinja_env.filters["montant"] = vues.fmt_montant

    with app.app_context():
        db.create_all()
        from .initial import semer
        semer()
    return app
