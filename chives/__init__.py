import os 
import typing as ty

from flask import Flask, request, jsonify, g
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chives.models import Base, Order, Transaction
from chives.matchingengine.matchingengine import MatchingEngine as ME

MAIN_DB = "chives.sqlite"


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
        DATABASE=os.path.join(app.instance_path, MAIN_DB)
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

    from chives.db import init_app 
    init_app(app)

    from chives.blueprints.auth import bp as auth_bp 
    from chives.blueprints.debug import bp as debug_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(debug_bp)
    
    return app
