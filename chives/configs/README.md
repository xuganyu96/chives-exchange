# Chives runtime configurations 
Both `chives.webserver.create_app` and `chives.matchingengine.start_engine` take `config: dict` as an argument. A configuration object is a dictionary whose keys are configuration names and whose values are used to dictate the behaviors of these two components, such as which database to connect to, and the credentials used for connecting to RabbitMQ.

## Configuration options
|config name|config value type|notes|
|`SQLALCHEMY_CONN`|String|The URI used to connect to the database|
|`RABBITMQ_HOST`|String|Hostname of the RabbitMQ server|
|`RABBITMQ_PORT`|Integer|Port of the RabbitMQ server|
|`RABBITMQ_VHOST`|String|Virtual host of the RabbitMQ server|
|`RABBITMQ_LOGIN`|String|Username of the RabbitMQ server|
|`RABBITMQ_PASSWORD`|String|Password of the RabbitMQ server|
