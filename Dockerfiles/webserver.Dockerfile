FROM python:3.8-buster

ENV CHIVES_VERSION='0.2.0'

# First create the 'chives' user and give it a home directory /home/chives
# All configuration files will placed directly under the home directory like 
# /home/chives/uwsgi.ini
RUN apt-get update \
    && apt-get install -y \
        vim \
        sudo \
        software-properties-common \
        netcat \
    && groupadd -g 501 chives \
    && useradd -g chives -u 501 -d /home/chives chives \
    && usermod -aG sudo chives \
    && mkdir /home/chives \
    && chown -R chives /home/chives \
    && pip install chives-exchange==${CHIVES_VERSION} uwsgi
COPY deploy/wsgi.py /home/chives/wsgi.py
COPY deploy/webserver.env.conf /home/chives/env.conf
COPY deploy/webserver.entrypoint.sh /home/chives/entrypoint.sh
RUN chmod a+x /home/chives/entrypoint.sh
EXPOSE 5000

USER chives
WORKDIR /home/chives
ENTRYPOINT ["/home/chives/entrypoint.sh"]
