import datetime as dt

from chives import Order, Transaction, engine as sql_engine
from chives.matchingengine import MatchingEngine
import pika

ask_1 = Order(security_symbol="AAPL", side="ask", size=100, price=100)
ask_2 = Order(security_symbol="AAPL", side="ask", size=100, price=99)
bid_1 = Order(security_symbol="AAPL", side="bid", size=120, price=101)
apple_engine = MatchingEngine("AAPL", sql_engine)

if __name__ == "__main__":
    msgs = [
        ask_1.to_json(),
        ask_2.to_json(),
        bid_1.to_json(),
    ]
    
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='AAPL')

    for msg in msgs:
        channel.basic_publish(exchange='', routing_key='AAPL', body=msg)
    connection.close()

    print(apple_engine.session.query(Order).count())
    print(apple_engine.session.query(Transaction).count())
