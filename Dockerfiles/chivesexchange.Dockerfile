FROM python:3.8-buster

ENV CHIVES_VERSION='0.2.2'

# System-wide dependencies, including chives-exchange library and uwsgi
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


COPY deploy/chives_entrypoint.py /home/chives/chives_entrypoint.py
COPY deploy/entrypoint.sh /home/chives/entrypoint.sh
RUN chmod a+x /home/chives/entrypoint.sh
EXPOSE 5000

USER chives
WORKDIR /home/chives
ENTRYPOINT ["/home/chives/entrypoint.sh"]
