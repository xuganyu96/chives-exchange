from flask import Blueprint

from flask_login import login_required, current_user

bp = Blueprint("debug", __name__, url_prefix="/debug")

@bp.route("/is_authenticated", methods=("GET",))
@login_required
def is_authenticated():
    return f"You are authenticated as {current_user.username}"
