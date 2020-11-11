import os 

from flask import Flask, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chives.models import Base, Order, Transaction

DATABASE = "/tmp/sqlite.db" 
engine = create_engine(f"sqlite:///{DATABASE}", echo=True)


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
            # TODO: implement this POST route such that it accepts a JSON object 
            # that can be parsed into an Order object. Once the order object 
            # is validated, send it into the order queue.
            incoming_json = request.data
            incoming_order = Order.from_json(incoming_json)
            print(incoming_order)
            return incoming_json
        else:
            sample_order = Order()
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
