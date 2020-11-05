import typing as ty
from sqlalchemy.engine import Engine as SQLEngine

from chives.engine import MatchingEngine
from chives.models import Order, Transaction

def test_aon_incoming(sql_engine: SQLEngine):
    """Test that for an all-or-none incoming order, the policy is properly 
    respected

    :param sql_engine: 
    :type sql_engine: SQLEngine
    """
    me = MatchingEngine("X", sql_engine)
    test_orders = [
        Order(order_id=1, security_symbol="X", side="ask", size=100, price=1),
        Order(order_id=2, security_symbol="X", side="bid", size=120, price=2,
                all_or_none=True)
    ]
    for test_order in test_orders:
        me.heartbeat(debug=True, incoming=test_order)
    
    # Order 1 is first entered into the order book
    # Order 2 then tries to match with order 1, but since order 1 is less than 
    # order 2, and order 2 has to be fulfilled entirely, no trade can be made 
    # and both orders are entered into the order book
    assert me.session.query(Transaction).count() == 0
    assert me.session.query(Order).count() == 2
    assert me.session.query(Order).get(1) is test_orders[0]
    assert me.session.query(Order).get(2) is test_orders[1]
    assert me.order_book.active_orders == {
        1: test_orders[0],
        2: test_orders[1]
    }
    assert test_orders[0].active
    assert test_orders[1].active


def test_aon_candidate(sql_engine: SQLEngine):
    """Test that for an all-or-none incoming order, the policy is properly 
    respected

    :param sql_engine: 
    :type sql_engine: SQLEngine
    """
    me = MatchingEngine("X", sql_engine)
    test_orders = [
        Order(order_id=1, security_symbol="X", side="ask", size=100, price=2,
                all_or_none=True),
        Order(order_id=2, security_symbol="X", side="ask", size=100, price=1),
        Order(order_id=3, security_symbol="X", side="bid", size=120, price=3)
    ]
    for test_order in test_orders:
        me.heartbeat(debug=True, incoming=test_order)
    
    # Order 1 and 2 are first entered into order book
    # When order 3 comes, it is first matched with order 2 to produce a trade
    # But the remaining of order 3 does not fulfill order 1 completely, so 
    # no trade is made. The remains of order 3 becomes a suborder with id 4
    # and that enters the order book
    order_4 = me.session.query(Order).get(4)

    assert me.session.query(Order).count() == 4
    assert me.session.query(Order).get(1) is test_orders[0]
    assert me.session.query(Order).get(2) is test_orders[1]
    assert me.session.query(Order).get(3) is test_orders[2]
    assert order_4.size == 20
    assert order_4.price == 3
    assert order_4.parent_order_id == 3
    


def test_simple_static_orders(sql_engine: SQLEngine):
    """Given a fixed set of orders, check that when each of them is entered,
    the matching occurs correctly

    :param sql_engine: the SQLAlchemy engine used for connecting to database
    :type sql_engine: SQLEngine
    """
    appl_engine = MatchingEngine("X", sql_engine)

    static_orders = [
        Order(order_id=1, security_symbol="X", side="ask", size=100, price=100),
        Order(order_id=2, security_symbol="X", side="ask", size=100, price=99),
        Order(order_id=3, security_symbol="X", side="bid", size=120, price=101)]
    for static_order in static_orders:
        appl_engine.heartbeat(debug=True, incoming=static_order)
    
    # Check at the end of the session that the active orders, the transactions, 
    # and the remaining orders. 
    transaction_1: Transaction = appl_engine.session.query(Transaction).get(1)
    transaction_2: Transaction = appl_engine.session.query(Transaction).get(2)
    assert transaction_1.ask_id == 2
    assert transaction_1.bid_id == 3
    assert transaction_1.size == 100
    assert transaction_1.price == 99
    
    assert transaction_2.ask_id == 1
    assert transaction_2.bid_id == 3
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

