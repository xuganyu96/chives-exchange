import os 
import typing as ty

from flask import Flask, request, jsonify, g
from flask_login import LoginManager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chives.models import Base, Order, Transaction
from chives.configs import environment_overwrite, DEFAULT_CONFIG


login_manager = LoginManager()

def create_app(config_overwrite: ty.Optional[ty.Dict] = None) -> Flask:
    """Create and configure the application

    :param config_overwrite: [description], defaults to None
    :type config_overwrite: [type], optional
    :return: a Flask application
    :rtype: Flask
    """
    # rc is short for runtime configuration
    rc = environment_overwrite(DEFAULT_CONFIG)
    if config_overwrite:
        rc.update(config_overwrite)

    # Create database schema if it doesn't exist
    sql_engine = create_engine(rc['SQLALCHEMY_CONN'])
    Base.metadata.create_all(sql_engine, checkfirst=True)

    # Create the application and set the runtime configuration
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(rc)

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
