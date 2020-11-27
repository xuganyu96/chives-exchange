from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from chives.db import get_db
from chives.models.models import Company, Transaction

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
    return jsonify(data)


@bp.route("/stock_chart_data", methods=("GET",))
@login_required 
def stock_chart_data():
    symbol = request.args['symbol']
    db = get_db()

    # Query all transactions with transaction dttm sorted from earlier to later
    symbol_filter = Transaction.security_symbol==symbol
    sort_key = Transaction.transact_dttm.asc()
    transactions = db.query(
        Transaction).filter(symbol_filter).order_by(sort_key).limit(100)
    
    data = {
        "labels": [t.transact_dttm.isoformat() for t in transactions],
        "datasets": [{
            "label": "Trade prices",
            "data": [{'t': t.transact_dttm.isoformat(), 'y': t.price} for t in transactions],
            "fill": False,
            "borderColor": "#1a73e8",
            "borderWidth": 1,
            "lineTension": 0
        }]
    }
    options = {
      "scales": {
        "xAxes": [{
          "type": 'time',
          "distribution": 'linear',
          "time": {
            "unit": 'second'
          }
        }]
      }
    }
    return jsonify({"data": data, "options": options})
