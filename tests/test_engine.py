import typing as ty
from sqlalchemy.engine import Engine as SQLEngine

from chives.engine import MatchingEngine
from chives.models import Order, Transaction

def test_simple_static_orders(sql_engine: SQLEngine):
    """Given a fixed set of orders, check that when each of them is entered,
    the matching occurs correctly

    :param sql_engine: the SQLAlchemy engine used for connecting to database
    :type sql_engine: SQLEngine
    """
    appl_engine = MatchingEngine("AAPL", sql_engine)

    static_orders = [
        Order(order_id=1, security_symbol="AAPL", side="ask", size=100, price=100),
        Order(order_id=2, security_symbol="AAPL", side="ask", size=100, price=99),
        Order(order_id=3, security_symbol="AAPL", side="bid", size=120, price=101)]
    for static_order in static_orders:
        appl_engine.heartbeat(debug=True, incoming=static_order)
    
    # Check at the end of the session that the active orders, the transactions, 
    # and the remaining orders. 
    transaction_1: Transaction = appl_engine.session.query(Transaction).get(1)
    transaction_2: Transaction = appl_engine.session.query(Transaction).get(2)
    assert transaction_1.ask_id == 2
    assert transaction_1.bid_id == 3
    assert transaction_1.security_symbol == "AAPL"
    assert transaction_1.size == 100
    assert transaction_1.price == 99
    
    assert transaction_2.ask_id == 1
    assert transaction_2.bid_id == 3
    assert transaction_2.security_symbol == "AAPL"
    assert transaction_2.size == 20
    assert transaction_2.price == 100

    order_1: Order = appl_engine.session.query(Order).get(1)
    order_2: Order = appl_engine.session.query(Order).get(2)
    order_3: Order = appl_engine.session.query(Order).get(3)
    order_4: Order = appl_engine.session.query(Order).get(4)
    assert order_1 is static_orders[0]
    assert order_2 is static_orders[1]
    assert order_3 is static_orders[2]
    assert order_4.parent_order_id == 1
    assert order_4.price == order_1.price 
    assert order_4.size == (order_1.size + order_2.size - order_3.size)

    assert appl_engine.order_book.active_orders == {4: order_4}

