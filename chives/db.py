import os

import click 
from flask import current_app, g, _app_ctx_stack
from flask.cli import with_appcontext
import pika
from sqlalchemy import create_engine 
from sqlalchemy.ext.declarative import declarative_base 
from sqlalchemy.orm import sessionmaker, scoped_session

SQLALCHEMY_URI = os.getenv("SQLALCHEMY_URI", "sqlite:////tmp/chives.sqlite")

engine = create_engine(SQLALCHEMY_URI)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    if 'db_session' not in g:
        g.db_session = scoped_session(
            Session, scopefunc=_app_ctx_stack.__ident_func__)
    return g.db_session

def close_db(e=None):
    db_session = g.pop('db_session', None)
    if db_session is not None:
        db_session.remove()
    
def init_db():
    db = get_db()
    Base.metadata.create_all(engine)

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
    return g.mq_conn

def close_mq(e=None):
    """Close the MQ connection; this method will be added to teardown_appcontext

    :param e: [description], defaults to None
    :type e: [type], optional
    """
    mq_conn: pika.BlockingConnection = g.pop('mq_conn', None)
    if mq_conn is not None:
        mq_conn.close()


@click.command("initdb")
@with_appcontext
def init_db_command():
    init_db()
    click.echo("Initialized database")

def init_app(app):
    app.teardown_appcontext(close_db)
    app.teardown_appcontext(close_mq)
    app.cli.add_command(init_db_command)