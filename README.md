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

**NEW!** Use MySQL as a backend database. For local environment, this is most 
easily achieved with a container:
```bash
docker run -d --rm \
    --name chives-mysql \
    -e MYSQL_RANDOM_ROOT_PASSWORD="yes" \
    -e MYSQL_DATABASE="chives" \
    -e MYSQL_USER="chives_u" \
    -e MYSQL_PASSWORD="chives_password" \
    -p 3307:3306 \
    -p 33061:33060 \
    mysql:8.0
```

Both the webserver and the matching engine reads from and writes to a SQL 
database, which by default is a SQLite located in `/tmp/chives.sqlite`. To 
initialize the database schema:
```bash
python -m chives initdb --sql-uri "mysql+pymysql://chives_u:chives_password@localhost:3307/chives"
```

Run the webserver and matching engine in two separate processes. Make sure that 
the matching engine is not erroring out because of failure to connect to 
RabbitMQ.
```bash
python -m chives start_engine --sql-uri "mysql+pymysql://chives_u:chives_password@localhost:3307/chives"
python -m chives webserver --sql-uri "mysql+pymysql://chives_u:chives_password@localhost:3307/chives"
```
