"""
All test cases written in this file test the orders only. The matching engine 
supplied in this module ignores user logic
"""
import pytest
from sqlalchemy.engine import Engine as SQLEngine
import typing as ty

from chives.matchingengine.matchingengine import MatchingEngine
from chives.models import Order, Transaction


@pytest.fixture
def matching_engine(sql_engine: SQLEngine) -> MatchingEngine:
    """Return a matching engine using the sql_engine obtained from top-level 
    fixture, and with user logic ignored

    :param sql_engine: [description]
    :type sql_engine: [type]
    :return: [description]
    :rtype: MatchingEngine
    """
    me = MatchingEngine(sql_engine, ignore_user_logic=True)
    return me


def test_aon_incoming(sql_engine: SQLEngine, matching_engine: MatchingEngine):
    """Test that for an all-or-none incoming order, the policy is properly 
    respected

    :param sql_engine: 
    :type sql_engine: SQLEngine
    """
    me = matching_engine
    test_orders = [
        Order(order_id=1, security_symbol="X", side="ask", size=100, price=1),
        Order(order_id=2, security_symbol="X", side="bid", size=120, price=2,
                all_or_none=True)
    ]
    for test_order in test_orders:
        me.heartbeat(incoming=test_order)
    
    # Order 1 is first entered into the order book
    # Order 2 then tries to match with order 1, but since order 1 is less than 
    # order 2, and order 2 has to be fulfilled entirely, no trade can be made 
    # and both orders are entered into the order book
    assert me.session.query(Transaction).count() == 0
    assert me.session.query(Order).count() == 2
    assert me.session.query(Order).get(1) is test_orders[0]
    assert me.session.query(Order).get(2) is test_orders[1]
    assert test_orders[0].active
    assert test_orders[1].active


def test_aon_candidate(sql_engine: SQLEngine, matching_engine: MatchingEngine):
    """Test that for an all-or-none incoming order, the policy is properly 
    respected

    :param sql_engine: 
    :type sql_engine: SQLEngine
    """
    me = matching_engine
    test_orders = [
        Order(order_id=1, security_symbol="X", side="ask", size=100, price=2,
                all_or_none=True),
        Order(order_id=2, security_symbol="X", side="ask", size=100, price=1),
        Order(order_id=3, security_symbol="X", side="bid", size=120, price=3)
    ]
    for test_order in test_orders:
        me.heartbeat(incoming=test_order)
    
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


def test_ioc_incoming(sql_engine: SQLEngine, matching_engine: MatchingEngine):
    """Check that the immediate-or-cancel policy is respected with an incoming 
    order

    :param sql_engine: [description]
    :type sql_engine: SQLEngine
    """
    me = matching_engine
    test_orders = [
        Order(order_id=1, security_symbol="X", side="ask", size=100, price=2),
        Order(order_id=2, security_symbol="X", side="bid", size=120, price=3,
                immediate_or_cancel=True)
    ]
    for test_order in test_orders:
        me.heartbeat(incoming=test_order)

    # order 1 is first entered into order book
    # When order 2 comes, it is first matched with order 1 to produce a trade 
    # and a sub-order of size 20 and priced at $3, but given the IOC policy,
    # this sub-order should be cancelled and not entered into the active orders
    order_3 = me.session.query(Order).get(3)
    transaction_1 = me.session.query(Transaction).get(1)

    assert me.session.query(Order).count() == 3
    assert me.session.query(Order).get(1) is test_orders[0]
    assert me.session.query(Order).get(2) is test_orders[1]
    assert order_3.cancelled_dttm is not None
    assert order_3.size == 20 
    assert order_3.price == 3
    assert order_3.parent_order_id == 2
    # assert len(me.order_book.active_orders) == 0
    assert transaction_1.ask_id == 1
    assert transaction_1.bid_id == 2
    assert transaction_1.price == 2
    assert transaction_1.size == 100


def test_market_order(sql_engine: SQLEngine, matching_engine: MatchingEngine):
    """Check that a market order, which has no price target and is IOC, can 
    trade properly

    :param sql_engine: [description]
    :type sql_engine: SQLEngine
    """
    me = matching_engine
    test_orders = [
        Order(order_id=1, security_symbol="X", side="ask", size=100, price=2),
        Order(order_id=2, security_symbol="X", side="bid", size=120, price=None,
                immediate_or_cancel=True)
    ]
    for test_order in test_orders:
        me.heartbeat(incoming=test_order)
    
    # Order 1 is first entered into order book
    # When order 2 comes, it is first matched with order 1 to produce a trade of 
    # 100 shares at $2, then the remaining 20 shares becomes a sub-order that 
    # is immediately cancelled
    order_3 = me.session.query(Order).get(3)
    transaction_1 = me.session.query(Transaction).get(1)

    assert me.session.query(Order).count() == 3
    assert me.session.query(Order).get(1) is test_orders[0]
    assert me.session.query(Order).get(2) is test_orders[1]
    assert order_3.cancelled_dttm is not None 
    assert order_3.size == 20
    assert order_3.price is None 
    assert order_3.parent_order_id == 2 
    # assert len(me.order_book.active_orders) == 0 
    assert transaction_1.ask_id == 1
    assert transaction_1.bid_id == 2
    assert transaction_1.price == 2
    assert transaction_1.size == 100 


def test_simple_static_orders(sql_engine: SQLEngine, matching_engine: MatchingEngine):
    """Given a fixed set of orders, check that when each of them is entered,
    the matching occurs correctly

    :param sql_engine: the SQLAlchemy engine used for connecting to database
    :type sql_engine: SQLEngine
    """
    me = matching_engine

    static_orders = [
        Order(order_id=0, security_symbol="Y", side="ask", size=100, price=100),
        Order(order_id=1, security_symbol="X", side="ask", size=100, price=100),
        Order(order_id=2, security_symbol="X", side="ask", size=100, price=99),
        Order(order_id=3, security_symbol="X", side="bid", size=120, price=101)]
    for static_order in static_orders:
        me.heartbeat(incoming=static_order)
    
    # Check at the end of the session that the active orders, the transactions, 
    # and the remaining orders. 
    transaction_1: Transaction = me.session.query(Transaction).get(1)
    transaction_2: Transaction = me.session.query(Transaction).get(2)
    assert transaction_1.ask_id == 2
    assert transaction_1.bid_id == 3
    assert transaction_1.size == 100
    assert transaction_1.price == 99
    
    assert transaction_2.ask_id == 1
    assert transaction_2.bid_id == 3
    assert transaction_2.size == 20
    assert transaction_2.price == 100

    order_1: Order = me.session.query(Order).get(1)
    order_2: Order = me.session.query(Order).get(2)
    order_3: Order = me.session.query(Order).get(3)
    order_4: Order = me.session.query(Order).get(4)
    assert order_1 is static_orders[1]
    assert order_2 is static_orders[2]
    assert order_3 is static_orders[3]
    assert order_4.parent_order_id == 1
    assert order_4.price == order_1.price 
    assert order_4.size == (order_1.size + order_2.size - order_3.size)
