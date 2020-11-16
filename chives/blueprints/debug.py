from flask import Blueprint

bp = Blueprint("debug", __name__, url_prefix="/debug")

@bp.route("/can_connect", methods=("GET",))
def can_connect():
    return "You are connected to chives exchange"