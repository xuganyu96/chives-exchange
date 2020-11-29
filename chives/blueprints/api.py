from collections import namedtuple
import datetime as dt
from math import floor
import typing as ty

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import pandas as pd

from chives.db import get_db
from chives.models.models import Company, Transaction

CandleStickDataPoint = namedtuple(
    # Respectively: dttm, open, high, low, close
    "CandleStickDataPoint", ["t", "o", "h", "l", "c"])
UNIX_START = dt.datetime(1970, 1, 1, 0, 0, 0)

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
        scale_unit = "hour"
    elif zoom == "month":
        cutoff -= dt.timedelta(days=30)
        agg_length = dt.timedelta(days=0.5)
        scale_unit = "day"
    elif zoom == "year":
        cutoff -= dt.timedelta(days=365)
        agg_length = dt.timedelta(days=1)
        scale_unit = "month"
    else:
        cutoff -= dt.timedelta(days=10*365)
        agg_length = dt.timedelta(days=7)
        scale_unit = "year"
    tfilter = tfilter & (Transaction.transact_dttm >= cutoff)

    sort_key = Transaction.transact_dttm.asc()
    query = db.query(Transaction).filter(tfilter).order_by(sort_key)

    # Convert the set of transactions into a 2 column dataframe: price vs dttm
    df = pd.read_sql(query.statement, db.bind)[['transact_dttm', 'price']]
    agg_data_points = aggregate_stock_chart(df, zoom)
    agg_data_points_dict = [{
        "t": dp.t * 1000,
        "o": dp.o,
        "h": dp.h,
        "l": dp.l,
        "c": dp.c,
        "y": dp.c
    } for dp in agg_data_points]
    max_price = 0 if pd.isna(df['price'].max()) else df['price'].max()
    min_price = 0 if pd.isna(df['price'].min()) else df['price'].min()
    price_std = 0 if pd.isna(df['price'].std()) else df['price'].std()
    
    data = {
        "labels": [],
        "datasets": [{
            "label": "market price",
            "data": agg_data_points_dict
        }]
    }
    options = {
        "scales": {
            "x": {
                "type": 'time',
                "distribution": 'linear',
                "time": {"unit": scale_unit}
            },
            "y": {
                "suggestedMax": max_price + 0.7 * price_std,
                "suggestedMin": max(0, min_price - 0.7 * price_std)
            }
        }
    }
    return jsonify({"data": data, "options": options})


def aggregate_stock_chart(df: pd.DataFrame, 
    zoom: str = "day") -> ty.List[ty.Dict]:
    """Given a DataFrame that contains two non-null columns "transact_dttm" and 
    "price", return a list of CandleStickDataPoint instances that represent the 
    aggregated trade data of the time interval that starts with dp.T and ends 
    with the next dp.T

    :param df: [description]
    :type df: pd.DataFrame
    :param zoom: [description], defaults to "day"
    :type zoom: str, optional
    """
    assert zoom in ["day", "month", "year", "max"]
    if zoom == "month":
        agg_tspan = dt.timedelta(hours=6)
    elif zoom == "year":
        agg_tspan = dt.timedelta(days=1)
    elif zoom == "max":
        agg_tspan = dt.timedelta(days=7)
    else:
        agg_tspan = dt.timedelta(minutes=10)
    
    global_min_transact_ts = df['transact_dttm'].min()
    global_agg_start = (global_min_transact_ts - UNIX_START) // agg_tspan \
        * agg_tspan + UNIX_START
    df['bucket_idx'] = (df['transact_dttm'] - global_agg_start) / agg_tspan
    df['bucket_idx'] = df['bucket_idx'].apply(floor)

    output = []
    for idx in df['bucket_idx'].unique():
        part = df.loc[df['bucket_idx'] == idx]
        open = round(part.sort_values('transact_dttm').head(1)['price'].values[0], 2)
        close = round(part.sort_values('transact_dttm').tail(1)['price'].values[0], 2)
        high = round(part['price'].max(), 2)
        low = round(part['price'].min(), 2)
        ts = (global_agg_start + idx * agg_tspan).timestamp()
        output.append(CandleStickDataPoint(
            t=ts, o=open, h=high, l=low, c=close
        ))
    
    return output
    
