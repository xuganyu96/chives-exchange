#!/bin/bash

# $1 is the argument passed in through docker command
echo $1

case "$1" in
    webserver)
        uwsgi --socket 0.0.0.0:5000 \
              --wsgi-file chives_entrypoint.py \
              --callable app \
              --processes 4 \
              --threads 2 \
              --stats 0.0.0.0:5001
        ;;
    matchingengine)
        python chives_entrypoint.py start_engine
        ;;
    *)
    echo $1
    ;;
esac
