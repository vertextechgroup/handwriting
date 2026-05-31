import os
from flask import Flask
from flask_cors import CORS

from .renderer.engine             import HandwritingRenderer
from .renderer.text_engine        import TextEngine
from .renderer.layout_engine      import LayoutEngine
from .renderer.paper_engine       import PaperEngine
from .renderer.pen_engine         import PenEngine
from .renderer.humanization_engine import HumanizationEngine
from .renderer.handwriting_engine  import HandwritingEngine
from .automation.bot              import HandwritingBot
from .services.job_service        import JobManager
from .routes.api                 import api_bp

__all__ = [
    "HandwritingRenderer",
    "TextEngine",
    "LayoutEngine",
    "PaperEngine",
    "PenEngine",
    "HumanizationEngine",
    "HandwritingEngine",
    "HandwritingBot",
    "create_app"
]

def create_app():
    app = Flask(__name__, 
                static_folder="../static", 
                template_folder="../templates")
    CORS(app)

    # Configuration
    app.config["UPLOAD_DIR"] = os.path.join("static", "uploads")
    app.config["GENERATED_DIR"] = os.path.join("static", "generated")
    app.config["PREVIEW_DIR"] = os.path.join("static", "previews")
    app.config["FONTS_DIR"] = os.path.join("static", "fonts")
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB

    # Ensure directories exist
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    os.makedirs(app.config["GENERATED_DIR"], exist_ok=True)
    os.makedirs(app.config["PREVIEW_DIR"], exist_ok=True)
    os.makedirs(app.config["FONTS_DIR"], exist_ok=True)

    # Initialize services
    app.job_manager = JobManager(app.config["GENERATED_DIR"], app.config["PREVIEW_DIR"])

    # Register blueprints
    app.register_blueprint(api_bp, url_prefix="")

    # Serve index.html
    @app.route("/")
    def index():
        from flask import render_template
        return render_template("index.html")

    return app
