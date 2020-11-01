import datetime as dt

from chives import session, Order, Transaction
from chives.matchingengine import OrderBook

if __name__ == "__main__":
    book = OrderBook(security="AAPL")

    ask_1 = Order(security="AAPL", side="ask", size=100, price=100) #   order_id 1
    ask_2 = Order(security="AAPL", side="ask", size=100, price=99) #    order_id 2
    bid_1 = Order(security="AAPL", side="bid", size=120, price=101) #   order_id 3

    # Test the buy-side algorithm
    book.match(ask_1)
    book.match(ask_2)
    book.match(bid_1)
    