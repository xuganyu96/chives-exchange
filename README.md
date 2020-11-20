# chives-exchange
Simulated stock exchange

## Run RabbitMQ with a single MatchingEngine
First, run the RabbitMQ container:

```bash
docker run --rm \
    --name "rabbitmq" \
    -p 5672:5672 \
    -p 15672:15672 \
    rabbitmq:3-management
```

Second run matching engine

Finally, run the test script to see if the system works.

## Run the flask application:
```bash
export FLASK_APP=chives
export FLASK_ENV=development

flask run
```