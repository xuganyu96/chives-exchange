import datetime as dt
import os
import sys
import typing as ty

import pika
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy.orm import sessionmaker

from chives.models import Base, Order, Transaction


_DEFAULT_OB_ENGINE = create_engine("sqlite:///:memory:", echo=False)


class OrderNotFoundError(KeyError):
    """The exception to raise when the orderbook instance is asked to retrieve 
    an order that does not exist in self.active_orders
    """
    pass


class OrderBook:
    """Abstraction of a limit order books that maintains active orders. The 
    state is maintained in a SQL database, which defaults to a SQLite database 
    held in memory. Using a SQL database allows graceful exit while preserving 
    the state. Note that the order book database's ID is consistent with the 
    main database's ID.
    """

    def __init__(self, sql_engine: SQLEngine = _DEFAULT_OB_ENGINE):
        """Upon instantiation, create the session object, and initialize the 
        database using the engine provided

        :param security_symbol: [description]
        :type security_symbol: str
        :param sql_engine: [description], defaults to _DEFAULT_OB_ENGINE
        :type sql_engine: SQLEngine, optional
        """
        Session = sessionmaker(bind=sql_engine)
        self.session = Session()

        # Create the table schemas if they don't exist; in addition, 
        # the order book is only concerned with orders, so there is no
        # need to create other tables
        Base.metadata.create_all(sql_engine, 
            [Base.metadata.tables[Order.__tablename__]], checkfirst=True)

    def get_order(self, order_id: int) -> Order:
        """Read an order by its order_id

        :param order_id: ID of the order to be obtained
        :type order_id: int
        :return: the order instance
        :rtype: Order
        """
        order = self.session.query(Order).get(order_id)
        if not order:
            raise OrderNotFoundError(f"Order ID {order_id} cannot be found")
        else:
            return order
    
    def get_candidates(self, incoming: Order) -> ty.List[Order]:
        """Given an incoming order, return all active orders that are on the 
        opposite sides, and that offer better price than the incoming order, if 
        the incoming order has a target price

        :param incoming: the incoming order
        :type incoming: Order
        :return: A list of candidate orders
        :rtype: ty.List[Order]
        """
        candidates: ty.List[Order] = []
        cond = (Order.security_symbol == incoming.security_symbol)
        sort_key = None
        if incoming.side == "bid":
            cond = cond & (Order.side == "ask")
            if incoming.price:
                cond = cond & (Order.price <= incoming.price)
            sort_key = Order.price.asc()
        else:
            cond = cond & (Order.side == "bid")
            if incoming.price:
                cond = cond & (Order.price >= incoming.price)
            sort_key = Order.price.desc()
        
        return self.session.query(Order).filter(cond).order_by(sort_key).all()


class MatchResult:
        """A dummy class for enforcing a schema for match result
        - incoming is an Order object attached to the main database's session
        - incoming_remain is one of three possibilities:
            - incoming itself
            - a session-less Order object (suborder of incoming)
            - None
        - deactivated is a list of order_id's that 
            - for corresponding entries in main db, change .active to False
            - remove from ob db
        - reactivated is a single sessionless Order object or None
        - transactions is a list of sessionless Transaction objects
        """
        def __init__(self):
            self.incoming: Order = None
            self.incoming_remain: Order = None 
            self.deactivated: ty.List[Order] = []
            self.reactivated: Order = None
            self.transactions: ty.List[Transaction] = []


class MatchingEngine:
    """Abstracting an instance of the matching engine, which wraps around the 
    order book instance and provides an algorithm for matching incoming orders 
    with active orders
    """

    def __init__(self, me_sql_engine: SQLEngine,
                       ob_sql_engine: SQLEngine = _DEFAULT_OB_ENGINE):
        """Initialize the matching engine by instantiating the order book and 
        creating a engine-bound session

        :param me_sql_engine: The engine for connecting to the main database
        :type me_sql_engine: SQLEngine
        :param ob_sql_engine: The engine for connecting to the order book 
        database, defaults to _DEFAULT_OB_ENGINE
        :type ob_sql_engine: SQLEngine, optional
        """
        self.ob = OrderBook(ob_sql_engine)

        Session = sessionmaker(bind=me_sql_engine)
        self.session = Session()
    
    @classmethod 
    def propose_trade(cls, incoming: Order, 
                           candidate: Order) -> ty.Optional[Transaction]:
        """Given the incoming order and a candidate order, return a Transaction 
        object that describes the trade that can happen between the two orders.
        If no trade can be proposed between the two orders, then None will be
        returned.

        :param incoming: the incoming order
        :type incoming: Order
        :param candidate: the candidate order
        :type candidate: Order
        :return: the proposed trade between the two order, or None if no trade 
        can be proposed
        :rtype: Transaction
        """
        # You can safely assume that incoming and candidate are on opposite 
        # sides and have matching target price, and that the candidate has a 
        # numeric target price
        if incoming.remaining_size <= 0 or candidate.remaining_size <= 0:
            return None 
        else:
            ask: Order = incoming if incoming.side == 'ask' else candidate 
            bid: Order = incoming if incoming.side == 'bid' else candidate
            # with the if statement above, transaction_size is guaranteed to 
            # be non-zero
            transaction_size = min(ask.remaining_size, bid.remaining_size)

            # Check if the candidate is all-or-none and accommodate it
            if candidate.all_or_none \
                and (transaction_size < candidate.remaining_size):
                    # If the candidate is all-or-none and the transaction 
                    # cannot fulfill it entirely
                    return None
            else:
                # the transaction size will always be the candidate's 
                # price since by prior filtering, the candidate will 
                # always have the better pricing

                transaction: Transaction = Transaction(
                    security_symbol=ask.security_symbol,
                    size=transaction_size,
                    price=candidate.price,
                    ask_id=ask.order_id,
                    bid_id=bid.order_id
                )

                return transaction
    
    def heartbeat(self, incoming: Order):
        """Register the incoming order into the main database, run it against 
        self.match, then commit the changes to main database and/or the 
        orderbook database

        :param incoming: the incoming order
        :type incoming: Order
        """
        if (incoming.order_id is None) \
            or (self.session.query(Order).get(incoming.order_id) is None):
            self.session.add(incoming)
            self.session.commit()

        # The self.match method does not commit any actual changes to any 
        # database. Instead, it returns the set of changes that need to be 
        # committed.
        match_result: MatchResult = self.match(incoming)

        # Read self.match's documentation for the fives types of database 
        # changes that can occur in a match. Here is how to deal with each of 
        # them:
        # 
        # Read the module README for how each type of match result is handled
        match_result.incoming = self.session.merge(match_result.incoming)
        self.session.commit()
        
        if match_result.incoming_remain is not match_result.incoming\
            and match_result.incoming_remain is not None:
            self.session.add(match_result.incoming_remain)
            self.session.commit()
        
        if match_result.incoming_remain is not None\
            and match_result.incoming_remain.active:
            self.ob.session.add(match_result.incoming_remain.copy())
            self.ob.session.commit()
        
        if len(match_result.deactivated) > 0:
            for deactivated in match_result.deactivated:
                main_entry = self.session.query(Order).get(deactivated)
                main_entry.active = False 
                main_entry = self.session.merge(main_entry)
                ob_entry = self.ob.session.query(Order).get(deactivated)
                self.ob.session.delete(ob_entry)
            self.session.commit()
            self.ob.session.commit()

        if match_result.reactivated is not None:
            self.session.add(match_result.reactivated)
            self.session.commit()
            self.ob.session.add(match_result.reactivated.copy())
            self.ob.session.commit()

        if len(match_result.transactions) > 0:
            for transaction in match_result.transactions:
                self.session.add(transaction)
            self.session.commit()
    
    def match(self, incoming: Order) -> MatchResult:
        """The specific logic is recorded in the module README.

        :param incoming: [description]
        :type incoming: Order
        :return: [description]
        :rtype: MatchResult
        """
        mr = MatchResult()
        incoming.remaining_size = incoming.size 
        candidates: ty.List[Order] = self.ob.get_candidates(incoming)

        for candidate in candidates:
            candidate.remaining_size = candidate.size

            if incoming.remaining_size <= 0:
                break
            else:
                # candidate's AON policy is respected within propose_trade;
                # if candidate is AON and incoming.remaining_size < candidate.size
                # then transaction is None
                transaction = self.propose_trade(incoming, candidate)
                if transaction is not None:
                    incoming.remaining_size -= transaction.size 
                    candidate.remaining_size -= transaction.size 
                    candidate.active = False
                    mr.transactions.append(transaction)
                    mr.deactivated.append(candidate.order_id)
                    # If the candidate is partially fulfilled, then create its 
                    # remains as a suborder
                    if candidate.remaining_size > 0:
                        mr.reactivated = candidate.create_suborder()
        
        # After all matchings are complete
        mr.incoming = incoming
        if incoming.remaining_size == incoming.size:
            mr.incoming_remain = mr.incoming
            mr.incoming_remain.active = True
        elif incoming.remaining_size > 0:
            mr.incoming_remain = incoming.create_suborder()
            mr.incoming_remain.active = True
        else:
            mr.incoming_remain = None

        # Respect the AON policy
        if incoming.all_or_none and incoming.remaining_size > 0:
            mr.incoming_remain = mr.incoming
            mr.incoming_remain.active = True
            mr.transactions = []
            # There is no need to refresh the candidate since each match() 
            # reads a fresh record from the database, which means the mutations 
            # in one match cycle does not persist to the next
            mr.deactivated = []
            mr.reactivated = None
        if incoming.immediate_or_cancel and (mr.incoming_remain is not None):
            mr.incoming_remain.cancelled_dttm = dt.datetime.utcnow()
            mr.incoming_remain.active = False
        
        return mr


def main(queue_host: str, sql_engine: SQLEngine):
    conn = pika.BlockingConnection(pika.ConnectionParameters(host=queue_host))
    ch = conn.channel()
    ch.queue_declare(queue="incoming_order")
    
    me = MatchingEngine(sql_engine)

    def msg_callback(ch, method, properties, body):
        print(" [x] Received %r" % body)
        me.heartbeat(Order.from_json(body))
    
    ch.basic_consume(queue="incoming_order", 
                     on_message_callback=msg_callback,
                     auto_ack=True)
    ch.start_consuming()


if __name__ == '__main__':
    SQLALCHEMY_ENGINE_URI = os.getenv("SQLALCHEMY_ENGINE_URI", 
                                      "sqlite:////tmp/sqlite.db")
    SECURTY_SYMBOL = os.getenv("SECURTY_SYMBOL", "AAPL")
    QUEUE_HOST = os.getenv("QUEUE_HOST", "localhost")
    sql = create_engine(SQLALCHEMY_ENGINE_URI, echo=True)

    try:
        main(QUEUE_HOST, sql, SECURTY_SYMBOL)
    except KeyboardInterrupt:
        print('Interrupted')
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
            
