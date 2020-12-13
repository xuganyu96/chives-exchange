# Chives Exchange 
`chives-exchange` is an implementation of an electronic stock exchange that contains a horizontally scalable matching engine and a web UI.

## Getting started
Chives exchange can be installed from pypi:
```
pip install chives-exchange
```

There are four main components of this implementation of stock exchange:
* Message queue
* SQL database 
* Matching engine(s)
* Webserver (optional)

### Message queue
Begin by starting a message queue server, which is the channel through which stock orders are picked up by matching engine(s) to match with resting orders in the orderbook and produce trades. The current implementation only supports RabbitMQ, which can be most easily run using a container:
```bash
docker run -d --rm \
    --name "rabbitmq" \
    -p 5672:5672 \
    -p 15672:15672 \
    rabbitmq:3-management
```

### Database
Chives exchange supports SQLite and MySQL as the backend database (other SQL databases might work; I just have not tested them). SQLite is a good choice for development, but won't allow multiple matching engines to be running at the same time; therefore, it is highly recommended that MySQL be used, which can be most easily accomplished through a container.

The `docker run` command below can be modified to use the username/password/database combination of your choice, just note that you will need them for the URI string later for the various commands.
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

After MySQL finished initializing, create the databases schemas by running the `initdb` command from the `chives` CLI:

```bash
python -m chives -v initdb \
    --sql-uri "mysql+pymysql://chives_u:chives_password@localhost:3307/chives"
```

The `-v` flag will set the SQLAlchemy engine to echo MySQL's response. It is optional but helpful as a first time to see what tables are created.

### Matching engine and webserver
Start an instance of a matching engine by calling `start_engine` and passing in the same SQL URI string as before:
```bash
python -m chives start_engine \
    --sql-uri "mysql+pymysql://chives_u:chives_password@localhost:3307/chives"
```
The matching engine will try to connect to the database and the message queue as soon as it starts; if the message queue or the database is not available, the matching engine will crash immediately. If the database is available, but the table schemas are not initialized, then the matching engine will crash when it starts processing stock orders.

The webserver offers a GUI for users to submit stock orders and do other things. It runs as a Flask application, and is started by calling `webserver`:
```bash
python -m chives webserver \
    --sql-uri "mysql+pymysql://chives_u:chives_password@localhost:3307/chives"
```



### Further readings
* [Trading for the first time](docs/trading_for_the_first_time.md)
