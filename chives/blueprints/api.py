from flask import Blueprint, jsonify
from flask_login import login_required, current_user

from chives.db import get_db
from chives.models.models import Company

bp = Blueprint("api", __name__, url_prefix="/api")

@bp.route("/is_authenticated", methods=("GET",))
@login_required
def is_authenticated():
    return jsonify(True)

@bp.route("/autocomplete_companies", methods=("GET",))
@login_required 
def autocomplete_companies():
    db = get_db()
    companies = db.query(Company).all()
    data = {c.symbol: None for c in companies}
    print(data)
    return jsonify(data)
