import datetime as dt

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import pandas as pd

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
    zoom = request.args['zoom'] if "zoom" in request.args else "year"
    db = get_db()

    # Query all transactions with transaction dttm sorted from earlier to later
    tfilter = (Transaction.security_symbol == symbol)
    # Add the dttm filter, which depends on the zoom level
    cutoff = dt.datetime.utcnow()
    agg_length = 0
    scale_unit = "day"
    if zoom == "day":
        cutoff -= dt.timedelta(hours=24)
        agg_length = dt.timedelta(minutes=5)
        scale_unit = "minute"
    elif zoom == "month":
        cutoff -= dt.timedelta(days=30)
        agg_length = dt.timedelta(days=1)
        scale_unit = "day"
    elif zoom == "year":
        cutoff -= dt.timedelta(days=365)
        agg_length = dt.timedelta(days=1)
        scale_unit = "day"
    else:
        cutoff -= dt.timedelta(days=10*365)
        agg_length = dt.timedelta(days=7)
        scale_unit = "week"
    tfilter = tfilter & (Transaction.transact_dttm >= cutoff)

    sort_key = Transaction.transact_dttm.asc()
    query = db.query(Transaction).filter(tfilter).order_by(sort_key)

    # Convert the set of transactions into a 2 column dataframe: price vs dttm
    df = pd.read_sql(query.statement, db.bind)[['transact_dttm', 'price']]
    df['td_from_min'] = df['transact_dttm'] - df['transact_dttm'].min()
    df['bucket_idx'] = (df['td_from_min'] / agg_length).astype(int)
    max_price = df['price'].max()
    min_price = df['price'].min()
    price_std = df['price'].std()
    dttm_price_pair = []
    for bucket in df['bucket_idx'].unique():
        partition = df.loc[df['bucket_idx'] == bucket]
        dttm_label = df['transact_dttm'].min() + bucket * agg_length
        price = partition.sort_values('transact_dttm')['price'].unique()[0]
        dttm_price_pair.append({'t': dttm_label, 'y': price})
    
    data = {
        # "labels": [t.transact_dttm.isoformat() for t in transactions],
        "datasets": [{
            "label": "market price",
            "data": dttm_price_pair,
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
                "time": {"unit": scale_unit}
            }],
            "yAxes": [{
                "ticks": {
                    "suggestedMax": max_price + 0.7 * price_std,
                    "suggestedMin": max(0, min_price - 0.7 * price_std)
                }
            }]
        }
    }
    return jsonify({"data": data, "options": options})
