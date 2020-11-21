import datetime as dt
import json
import time

from sqlalchemy import create_engine
import pika

from chives.db import SQLALCHEMY_URI
from chives.models import Order, Transaction
from chives.matchingengine.matchingengine import MatchingEngine

ask_1 = Order(security_symbol="AAPL", side="ask", size=100, price=100)
ask_2 = Order(security_symbol="AAPL", side="ask", size=100, price=99)
bid_1 = Order(security_symbol="AAPL", side="bid", size=120, price=101)
sql_engine = create_engine(SQLALCHEMY_URI, echo=False)
apple_engine = MatchingEngine(sql_engine)

if __name__ == "__main__":
    msgs = [
        ask_1.json,
        ask_2.json,
        bid_1.json,
    ]
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='incoming_order')

    for msg in msgs:
        channel.basic_publish(
            exchange='', routing_key='incoming_order', body=msg)
    connection.close()

    print("Wait for 1 second!")
    time.sleep(1)
    print(apple_engine.session.query(Order).count())
    print(apple_engine.session.query(Transaction).count())
