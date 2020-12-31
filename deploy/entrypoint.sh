#!/bin/bash

# $1 is the argument passed in through docker command
echo $1

case "$1" in
    webserver)
        uwsgi --socket 127.0.0.1:5000 \
              --wsgi-file chives_entrypoint.py \
              --callable app \
              --processes 4 \
              --threads 2 \
              --stats 127.0.0.1:5001
        ;;
    matchingengine)
        python chives_entrypoint.py start_engine
        ;;
    *)
    echo $1
    ;;
esac
