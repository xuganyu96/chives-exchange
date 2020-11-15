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
    
    return app
