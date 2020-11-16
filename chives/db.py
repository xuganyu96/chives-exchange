import click
from flask import current_app, g 
from flask.cli import with_appcontext
from sqlalchemy import create_engine 
from sqlalchemy.orm import sessionmaker


def get_session():
    if 'main_db_session' not in g:
        Session = sessionmaker(
            create_engine(f"sqlite:///{current_app.config['DATABASE']}"))
        g.main_db_session = Session()
    
    return g.main_db_session

def init_db():
    engine = create_engine(f"sqlite:///{current_app.config['DATABASE']}")
    from .models import Base 
    Base.metadata.create_all(engine)

@click.command('initdb')
@with_appcontext 
def init_db_command():
    init_db()
    click.echo("Initialized ORM schemas")


def init_app(app):
    app.cli.add_command(init_db_command)