from flask import Blueprint, render_template_string

from config_store import default_output_dir
from web_ui import HTML


pages_bp = Blueprint("pages", __name__)


@pages_bp.get("/")
def home():
    return render_template_string(HTML, default_output_dir=default_output_dir())

