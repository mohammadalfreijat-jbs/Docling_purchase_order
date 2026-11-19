"""Flask application factory."""

from flask import Flask

from app.config import config


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="../static",
    )
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    from app.routes.views import bp
    app.register_blueprint(bp)

    return app
