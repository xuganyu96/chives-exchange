import os
import logging

import click 
from flask import current_app, g, _app_ctx_stack
from flask.cli import with_appcontext
import pika
from sqlalchemy import create_engine 
from sqlalchemy.ext.declarative import declarative_base 
from sqlalchemy.orm import sessionmaker, scoped_session

DEFAULT_SQLALCHEMY_URI = "sqlite:////tmp/chives.sqlite"
SQLALCHEMY_URI = os.getenv("SQLALCHEMY_URI", "sqlite:////tmp/chives.sqlite")

# engine = create_engine(SQLALCHEMY_URI)
# Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
logger = logging.getLogger("chives.webserver")
chandle = logging.StreamHandler()
formatter = logging.Formatter(
    '[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s')
chandle.setFormatter(formatter)
logger.addHandler(chandle)
Base = declarative_base()


def get_db():
    if 'db_session' not in g:
        database_uri = current_app.config['DATABASE_URI']
        engine = create_engine(database_uri)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        g.db_session = scoped_session(
            Session, scopefunc=_app_ctx_stack.__ident_func__)
        logger.debug(f"Spawned scoped session for webserver: {database_uri}")
    return g.db_session

def close_db(e=None):
    db_session = g.pop('db_session', None)
    if db_session is not None:
        db_session.remove()
    logger.debug(f"ORM Session closed")

def get_mq() -> pika.BlockingConnection:
    """If the webserver application has no active connection to the RabbitMQ 
    server, then create one and append it to the flask G. Otherwise, return 
    the connection on the flask G

    :return: an active connection
    :rtype: pika.BlockingConnection
    """
    if 'mq_conn' not in g:
        g.mq_conn = pika.BlockingConnection(
            pika.ConnectionParameters(host='localhost'))
        logger.debug(f"Spawned RabbitMQ connection")
    return g.mq_conn

def close_mq(e=None):
    """Close the MQ connection; this method will be added to teardown_appcontext

    :param e: [description], defaults to None
    :type e: [type], optional
    """
    mq_conn: pika.BlockingConnection = g.pop('mq_conn', None)
    if mq_conn is not None:
        mq_conn.close()
    logger.debug(f"Closed RabbitMQ connection")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.teardown_appcontext(close_mq)
