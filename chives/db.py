import os

import click 
from flask import current_app, g, _app_ctx_stack
from flask.cli import with_appcontext
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

@click.command("initdb")
@with_appcontext
def init_db_command():
    init_db()
    click.echo("Initialized database")

def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)