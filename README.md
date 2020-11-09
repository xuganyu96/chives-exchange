# chives-exchange
Simulated stock exchange

# Run RabbitMQ with a single MatchingEngine
First, run the RabbitMQ container:

```bash
docker run --rm \
    --name "rabbitmq" \
    -p 5672:5672 \
    -p 15672:15672 \
    rabbitmq:3-management
```

Second, build and run the matching engine container

```bash
docker build \
    -t chives-me:dev \
    -f Dockerfiles/matchingEngine.Dockerfile \
    .

docker run --rm \
    --name "chives-me" \
    --network host \
    --volume /tmp:/tmp \
    chives-me:dev
```

Finally, run the test script to see if the system works.