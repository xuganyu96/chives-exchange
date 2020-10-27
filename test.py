import datetime as dt

from chives import session, Order, Transaction
from chives.orderbook import OrderBook

def match(book: OrderBook, incoming: Order, session=session):
    session.add(incoming)
    session.commit()

    transactions = []

    if incoming.side == "bid":
        incoming_bid = incoming 
        candidate_asks = book.get_orders(lambda o: o.side == "ask")

        if incoming_bid.price:
            candidate_asks = book.get_orders(
                lambda o: (o.side == "ask") and (o.price <= incoming_bid.price)
            )
        
        candidate_asks.sort(key=lambda o: o.price)
        matched_asks = []
        for candidate_ask in candidate_asks:
            if not incoming_bid.size <= 0:
                if (incoming_bid.size >= candidate_ask.size) \
                    or (not candidate_ask.all_or_none):
                    transaction_size = min(incoming_bid.size, candidate_ask.size)
                    transactions.append(Transaction(
                        security=candidate_ask.security,
                        ask_id=candidate_ask.id,
                        bid_id=incoming_bid.id,
                        size=transaction_size,
                        price=candidate_ask.price
                    ))
                    incoming_bid.size -= transaction_size
                    candidate_ask.size -= transaction_size
                    matched_asks.append(candidate_ask)
    
        remaining_bid = incoming_bid.copy()
        if incoming_bid.all_or_none and remaining_bid.size > 0:
            session.refresh(incoming_bid)
            remaining_bid = incoming_bid
            for candidate_ask in matched_asks:
                session.refresh(candidate_ask)
            transactions = []
        if incoming_bid.immediate_or_cancel and remaining_bid.size > 0:
            remaining_bid.cancelled_dttm = dt.datetime.utcnow()
        if remaining_bid.size > 0 and remaining_bid.cancelled_dttm is None:
            book.register(remaining_bid)
        if remaining_bid.size > 0:
            session.add(remaining_bid)
            session.commit()
        
        for transaction in transactions:
            session.add(transaction)
            session.commit()
            matched_ask = book.deregister(transaction.ask_id)
            if matched_ask.size > 0:
                remaining_ask = matched_ask.copy()
                session.add(remaining_ask)
                session.commit()
                book.register(remaining_ask)

if __name__ == "__main__":
    book = OrderBook(security="AAPL")

    ask_1 = Order(security="AAPL", side="ask", size=100, price=100)
    ask_2 = Order(security="AAPL", side="ask", size=100, price=99)
    buy_1 = Order(security="AAPL", side="bid", size=120, price=101)

    # Test the buy-side algorithm
    session.add_all([ask_1, ask_2])
    session.commit()
    book.register(ask_1)
    book.register(ask_2)

    # TODO: verify that after this method runs, the orders and order_book is in correct state
    match(book, buy_1, session=session)
    