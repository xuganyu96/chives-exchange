import os 
import typing as ty

from flask import Flask, request, jsonify, g
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chives.models import Base, Order, Transaction
from chives.matchingengine.matchingengine import MatchingEngine as ME

DATABASE = "/tmp/sqlite.db" 
me_engine = create_engine(f"sqlite:///{DATABASE}", echo=True)


def create_app(test_config = None) -> Flask:
    """Create and configure the application

    :param test_config: [description], defaults to None
    :type test_config: [type], optional
    :return: a Flask application
    :rtype: Flask
    """
    # Note that __name__ evaluates to chives in this instance
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DATABASE=DATABASE
    )
    with app.app_context():
        g.matching_engines: ty.Dict[str, ME] = dict()

    if test_config is None:
        app.config.from_pyfile('config.py', silent=True)
    else:
        app.config.from_mapping(test_config) 

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    @app.route("/debug/can_connect")
    def hello():
        return "You are connected to chives exchange"
    
    @app.route("/api/submit_order", methods=("GET", "POST"))
    def submit_order():
        if request.method == "POST":
            incoming_json = request.data
            incoming_order = Order.from_json(incoming_json)
            if incoming_order.security_symbol not in g.matching_engines:
                ob_engine = create_engine(
                    f"sqlite:////tmp/chives_{ob_engine}.ob.sqlite")
                with app.app_context():
                    g.matching_engines[incoming_order.security_symbol] = ME(
                        incoming_order.security_symbol,
                        me_engine, ob_engine
                    )
            me: ME = g.matching_engines[incoming_order.security_symbol]
            me.heartbeat(incoming_order)
            return incoming_json
        else:
            return jsonify({
                'order_id': "Integer",
                'security_symbol': "String",
                'side': "Either ask or bid",
                'size': "Positive integer",
                'price': "Positive float or null",
                'all_or_none': "true or false",
                'immediate_or_cancel': "true or false",
                'active': "true or false",
                'parent_order_id': "Integer or null",
                'cancelled_dttm': "null"
            })
    
    return app
