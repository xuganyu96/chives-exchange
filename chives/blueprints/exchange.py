from flask import (
    Blueprint, flash, g as flask_g, redirect, render_template, request, 
    session as flask_session, url_for
)
from flask_login import login_required, current_user

bp = Blueprint("exchange", __name__, url_prefix="/exchange")

@bp.route("/dashboard", methods=("GET",))
@login_required
def dashboard():
    return render_template("exchange/dashboard.html")
