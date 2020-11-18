from flask import Blueprint

from flask_login import login_required

bp = Blueprint("debug", __name__, url_prefix="/debug")

@bp.route("/can_connect", methods=("GET",))
@login_required
def can_connect():
    return "You are connected to chives exchange"