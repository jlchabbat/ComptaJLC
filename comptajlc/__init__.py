import os

from flask import Flask

from .models import db


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("COMPTAJLC_SECRET", "dev-a-changer"),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(app.instance_path, "compta.db"),
    )
    if config:
        app.config.update(config)
    db.init_app(app)

    from . import vues
    app.register_blueprint(vues.bp)
    app.jinja_env.filters["montant"] = vues.fmt_montant

    with app.app_context():
        db.create_all()
        from .initial import semer
        semer()
    return app
