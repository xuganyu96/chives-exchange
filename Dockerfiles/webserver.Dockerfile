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

EXPOSE 5000
USER chives
WORKDIR /home/chives
COPY deploy/wsgi.py /home/chives/wsgi.py

ENTRYPOINT ["uwsgi", "--socket", "0.0.0.0:5000", "--protocol", "http", "-w", "wsgi:app"]
