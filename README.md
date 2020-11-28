# chives-exchange
Implementation of a stock exchange with matching engine and a web UI powered by 
Flask.

## Getting started
The webserver communicates to the matching engine through RabbitMQ, which can be 
most easily run using docker:
```bash
docker run -d --rm \
    --name "rabbitmq" \
    -p 5672:5672 \
    -p 15672:15672 \
    rabbitmq:3-management
```

Both the webserver and the matching engine reads from and writes to a SQL 
database, which by default is a SQLite located in `/tmp/chives.sqlite`. To 
initialize the database schema:
```bash
python -m chives initdb
```

Run the webserver and matching engine in two separate processes. Make sure that 
the matching engine is not erroring out because of failure to connect to 
RabbitMQ.
```bash
python -m chives start_engine
python -m chives webserver
```

You can now follow the demo [here](https://xuganyu96.github.io/chives-exchange/) 
to try it out, or you can run `reset_and_simulate.py` to inject dummy users and 
trades, then sign-in to `buyer` or `seller` with dummy `password` to explore 
the UI.
