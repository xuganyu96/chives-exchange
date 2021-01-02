# Deploy to AWS EC2 (or other virtual machines)
A minimum of 5 containers are for deployment: `mysql`, `rabbitmq`, `webserver`, `matchingengine`, and `nginx`. All five containers will be connected to a standalone bridge network named `chives-net` to be isolated from the host network, and only `nginx` port 80 mapped to port 80 on the host machine.

Below are the run commands for creating the docker network, then running the containers. To teardown, stop all containers and remove the network.
```
## Create the docker network 
docker network create chives_net

## MySQL
docker run \
    --name mysql \
    --network chives_net \
    -e MYSQL_RANDOM_ROOT_PASSWORD="yes" \
    -e MYSQL_DATABASE="chives" \
    -e MYSQL_USER="chives_u" \
    -e MYSQL_PASSWORD="chives_password" \
    -d --rm  mysql:8.0

## RabbitMQ
docker run \
    --name "rabbitmq" \
    --network chives_net \
    -d --rm  rabbitmq:3-management

## Webserver
docker run \
    --name "webserver" \
    --network chives_net \
    -e "SQLALCHEMY_CONN=mysql+pymysql://chives_u:chives_password@mysql:3306/chives" \
    -e "RABBITMQ_HOST=rabbitmq" \
    -d --rm  chivesexchange:latest webserver

## Matching engine 
docker run \
    --name "matchingengine" \
    --network chives_net \
    -e "SQLALCHEMY_CONN=mysql+pymysql://chives_u:chives_password@mysql:3306/chives" \
    -e "RABBITMQ_HOST=rabbitmq" \
    -d --rm  chivesexchange:latest matchingengine

## NginX
docker run \
    --name "nginx" \
    --network chives_net \
    -p 80:80 \
    -v $HOME/chives-exchange/deploy/nginx.conf:/etc/nginx/nginx.conf:ro \
    -d --rm  nginx:1.19.6
```