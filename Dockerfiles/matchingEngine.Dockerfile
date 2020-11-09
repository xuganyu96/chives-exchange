FROM python:3.8-buster

COPY chives /chives 
COPY requirements.txt /requirements.txt 
RUN python -m pip install -r requirements.txt

ENTRYPOINT ["python", "-m", "chives.matchingengine"]