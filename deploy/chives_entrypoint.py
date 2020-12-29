"""Import the runtime configuration (as a Python dictionary) from 
chives_config.py from the same directory as this file, then import create_app 
from chives.webserver and create the Flask application object by passing in 
the configuration object. 

In case the docker image is run with command "webserver", the shell entrypoint 
script will call:
    uwsgi [OPTIONS] -w chives_entrypoint:app
to run the application object

In case the docker image is run with command "matchingengine", the shell 
entrypoint will call:
    python chives_entrypoint.py start_engine
which should invoke this python entrypoint's __main__ method, within which 
chives.matchingengine.start_engine will be called with the configuration object 
passed.
"""
import sys
from sqlalchemy import create_engine
from chives.webserver import create_app 
from chives.matchingengine import start_engine 

from chives_config import CONFIG


# Adapt the global config to Flask application config
flask_config = CONFIG.copy()
flask_config['DATABASE_URI'] = flask_config['sql_alchemy_conn']
app = create_app(CONFIG)

if __name__ == "__main__":
    if sys.argv[1] == "start_engine":
        sql_engine = create_engine(CONFIG['sql_alchemy_conn'])
        start_engine(CONFIG['rabbitmq_host'], sql_engine)