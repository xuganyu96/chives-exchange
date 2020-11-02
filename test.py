import datetime as dt

from chives import Order, Transaction, engine as sql_engine
from chives.engine import MatchingEngine

ask_1 = Order(security_symbol="AAPL", side="ask", size=100, price=100)
ask_2 = Order(security_symbol="AAPL", side="ask", size=100, price=99)
bid_1 = Order(security_symbol="AAPL", side="bid", size=120, price=101)
apple_engine = MatchingEngine("AAPL", sql_engine)

if __name__ == "__main__":
    apple_engine.heartbeat(debug=True, incoming=ask_1)
    apple_engine.heartbeat(debug=True, incoming=ask_2)
    apple_engine.heartbeat(debug=True, incoming=bid_1)

    print(apple_engine.session.query(Transaction).all())
    print(apple_engine.session.query(Order).all())
