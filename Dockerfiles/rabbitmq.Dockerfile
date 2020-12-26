FROM rabbitmq:3.8

COPY deploy/dev.env.conf /usr/local/bin/env.conf
