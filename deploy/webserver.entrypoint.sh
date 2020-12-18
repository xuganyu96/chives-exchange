#!/bin/bash

# Use webserver.env.conf to load environment variables that wsgi.py will pick 
# up and pass into the Flask application. Call initdb to create SQL tables, 
# then start the uwsgi webserver
source ./env.conf

python -m chives -v initdb --sql-uri $SQL_URI

uwsgi --socket 0.0.0.0:5000 --protocol uwsgi -w wsgi:app
