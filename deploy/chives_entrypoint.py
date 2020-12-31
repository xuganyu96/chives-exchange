"""All of runtime configurations are set using environment variables. This is 
okay because both create_app and start_engine will overwrite the default 
configuration stored in chives.configs.DEFAULT_CONFIG using identically named 
environment variables.

In case the docker image is run with command "webserver", the shell entrypoint 
script will call the equivalent of:
    uwsgi [OPTIONS] -w chives_entrypoint:app
to run the application object

In case the docker image is run with command "matchingengine", the shell 
entrypoint will call:
    python chives_entrypoint.py start_engine
which should invoke this python entrypoint's __main__ method, within which 
chives.matchingengine.start_engine will be called.
"""
import sys
from sqlalchemy import create_engine
from chives.webserver import create_app 
from chives.matchingengine import start_engine 

# Flask application created for uwsgi 
app = create_app()

if __name__ == "__main__":
    if sys.argv[1] == "start_engine":
        start_engine()