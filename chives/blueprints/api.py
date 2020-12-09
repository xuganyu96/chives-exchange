from collections import namedtuple
import datetime as dt
from math import floor
import random
import typing as ty

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
import pandas as pd

from chives.db import get_db
from chives.models import Company, Transaction

CandleStickDataPoint = namedtuple(
    # Respectively: dttm, open, high, low, close
    "CandleStickDataPoint", ["t", "o", "h", "l", "c"])
ZoomConfig = namedtuple("ZoomConfig", ['cutoff_offset', 'scale_unit', 'agg_tspan'])
UNIX_START = dt.datetime(1970, 1, 1, 0, 0, 0)
ZOOM_CONFIGS = {
    'day': ZoomConfig(dt.timedelta(hours=24), "hour", dt.timedelta(minutes=10)),
    'month': ZoomConfig(dt.timedelta(days=30), "day", dt.timedelta(hours=6)),
    'year': ZoomConfig(dt.timedelta(days=365), "month", dt.timedelta(days=1)),
    'max': ZoomConfig(dt.timedelta(days=3650), "year", dt.timedelta(days=7))
}

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
    debug = int(request.args['debug']) if "debug" in request.args else 0
    db = get_db()

    # Query all transactions with transaction dttm sorted from earlier to later
    tfilter = (Transaction.security_symbol == symbol)
    # Add the dttm filter, which depends on the zoom level
    cutoff = dt.datetime.utcnow() - ZOOM_CONFIGS[zoom].cutoff_offset
    scale_unit = ZOOM_CONFIGS[zoom].scale_unit
    tfilter = tfilter & (Transaction.transact_dttm >= cutoff)

    sort_key = Transaction.transact_dttm.asc()
    query = db.query(Transaction).filter(tfilter).order_by(sort_key)

    # Convert the set of transactions into a 2 column dataframe: price vs dttm
    df = pd.read_sql(query.statement, db.bind)[['transact_dttm', 'price']]
    if debug:
        # If debug is set to True, then return dummy data without reading
        # from database
        random.seed(10)
        df = pd.DataFrame({
            "transact_dttm": [
                dt.datetime.fromtimestamp(
                    random.uniform(
                        cutoff.timestamp(),
                        dt.datetime.utcnow().timestamp()
                    )
                )  for i in range(500)],
            "price": [random.uniform(10, 100) for i in range(500)]
        }).sort_values('transact_dttm')
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
    if df.shape[0] == 0:
        # If there is no transaction, then return an empty list
        return []
    
    assert zoom in ["day", "month", "year", "max"]
    agg_tspan = ZOOM_CONFIGS[zoom].agg_tspan
    
    global_min_transact_ts = df['transact_dttm'].min()
    global_agg_start = (global_min_transact_ts - UNIX_START) // agg_tspan \
        * agg_tspan + UNIX_START
    df['bucket_idx'] = (df['transact_dttm'] - global_agg_start) / agg_tspan
    df['bucket_idx'] = df['bucket_idx'].apply(floor)

    output = []
    # an interval's close should be next interval's open
    prior_close = None
    for idx in df['bucket_idx'].unique():
        part = df.loc[df['bucket_idx'] == idx]
        # If there is a prior close, then open is set to prior close
        open = prior_close if prior_close else round(
            part.sort_values('transact_dttm').head(1)['price'].values[0], 2)
        # Update prior close
        prior_close = close = round(
            part.sort_values('transact_dttm').tail(1)['price'].values[0], 2)
        high = round(part['price'].max(), 2)
        low = round(part['price'].min(), 2)
        ts = (global_agg_start + idx * agg_tspan).timestamp()
        output.append(CandleStickDataPoint(
            t=ts, o=open, h=high, l=low, c=close
        ))
    
    return output
    