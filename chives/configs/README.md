# Chives runtime configurations 
Both `chives.webserver.create_app` and `chives.matchingengine.start_engine` take `config: dict` as an argument. A configuration object is a dictionary whose keys are configuration names and whose values are used to dictate the behaviors of these two components, such as which database to connect to, and the credentials used for connecting to RabbitMQ.

All configurations have a default values, which will be the ultimate fallback if no other inputs are given. The default configuratoin can be found under `chives.configs.default_config.py`

## Configuration options
|config name|config value type|notes|
|`SQLALCHEMY_CONN`|String|The URI used to connect to the database|
|`RABBITMQ_HOST`|String|Hostname of the RabbitMQ server|
|`RABBITMQ_PORT`|Integer|Port of the RabbitMQ server|
|`RABBITMQ_VHOST`|String|Virtual host of the RabbitMQ server|
|`RABBITMQ_LOGIN`|String|Username of the RabbitMQ server|
|`RABBITMQ_PASSWORD`|String|Password of the RabbitMQ server|
|`MATCHING_ENGINE_DRY_RUN`|Boolean|True if and only if matching engine does not heartbeat upon receiving message|