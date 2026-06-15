from flask import Flask
from config.settings import ENABLE_DATABASE


def create_app() -> Flask:
    app = Flask(__name__)

    if ENABLE_DATABASE:
        try:
            from app.db import init_db
            init_db()
        except Exception as exc:
            app.logger.warning("Database init skipped: %s", exc)

    from app.routes import bp
    app.register_blueprint(bp)

    return app
