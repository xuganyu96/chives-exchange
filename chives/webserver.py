import os 
import typing as ty

from flask import Flask, request, jsonify, g
from flask_login import LoginManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chives.models import Base, Order, Transaction


login_manager = LoginManager()

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
        SECRET_KEY='dev'
    )

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
    login_manager.init_app(app)

    from chives.blueprints.auth import bp as auth_bp 
    from chives.blueprints.debug import bp as debug_bp
    from chives.blueprints.exchange import bp as ex_bp
    from chives.blueprints.api import bp as api_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(ex_bp)
    app.register_blueprint(api_bp)
    
    return app
