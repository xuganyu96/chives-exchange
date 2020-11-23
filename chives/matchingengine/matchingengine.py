import datetime as dt
import os
import sys
import typing as ty

import pika
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy.orm import sessionmaker, Session

from chives.models.models import Base, Order, Transaction, Asset, User, Company


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

    def __init__(self, main_db_session: Session):
        """The main_db_session is most likely going to be passed in by the 
        matching engine, but for debugging purpose, other sessions can be 
        passed in, as well

        :param main_db_session: [description]
        :type main_db_session: Session
        """
        self.session = main_db_session

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
        """Given an incoming order, return all active orders of the same 
        security symbol, that are on the opposite sides, and that offer better 
        price than the incoming order, if the incoming order has a target price

        :param incoming: the incoming order
        :type incoming: Order
        :return: A list of candidate orders
        :rtype: ty.List[Order]
        """
        candidates: ty.List[Order] = []
        cond = (Order.security_symbol == incoming.security_symbol) \
            & (Order.active == True)
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
                       ignore_user_logic: bool = False):
        """Initialize the matching engine by instantiating the order book and 
        creating a engine-bound session

        :param me_sql_engine: The engine for connecting to the main database
        :type me_sql_engine: SQLEngine
        :param ignore_user_logic: if True, the matching engine will not modify 
        user assets after transactions are committed. Defaults to False
        :type ignore_user_logic: bool
        """
        Session = sessionmaker(bind=me_sql_engine)
        self.session = Session()
        self.ob = OrderBook(self.session)
        self.ignore_user_logic = ignore_user_logic
    
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
        # The canonical way of receiving orders is from order submissions 
        # from webserver to the order queue, and since the webserver already 
        # commits the order into the main database, there should not be the 
        # need to commit to the main database again.
        # However, for debugging and testing purposes, we allow uncommitted 
        # Order objects to be entered, hence the logic below for checking 
        # whether the incoming order is in the main database or not.
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
        #
        self.session.merge(match_result.incoming)
        self.session.commit()
        
        if match_result.incoming_remain is not match_result.incoming\
            and match_result.incoming_remain is not None:
            self.session.add(match_result.incoming_remain)
            self.session.commit()
        
        
        if len(match_result.deactivated) > 0:
            for deactivated in match_result.deactivated:
                main_entry = self.session.query(Order).get(deactivated)
                main_entry.active = False 
            self.session.commit()

        if match_result.reactivated is not None:
            self.session.add(match_result.reactivated)
            self.session.commit()

        if len(match_result.transactions) > 0:
            for transaction in match_result.transactions:
                self.session.add(transaction)
                self.session.commit()
                if not self.ignore_user_logic:
                    # Identify the seller and the buyer.
                    ask = self.session.query(Order).get(transaction.ask_id)
                    bid = self.session.query(Order).get(transaction.bid_id)
                    seller: User = ask.owner
                    buyer: User = bid.owner

                    # Seller gains cash and loses stocks, but the stock share 
                    # deduction happens at order's submission, so we only need 
                    # to be concerned with gaining cash.
                    cash_volume = transaction.price * transaction.size 
                    seller_cash: Asset = self.session.query(Asset).get(
                        (seller.user_id, "_CASH")
                    )
                    seller_cash.asset_amount += cash_volume
                    self.session.commit()

                    # Buyer gains stock and loses cash, both of which will 
                    # happen here, since there is no telling what price the 
                    # buyer will get when the buyer places an order.
                    #
                    # First check if the buyer has had this kind of asset before
                    buyer_stock = self.session.query(Asset).get(
                        (buyer.user_id, transaction.security_symbol)
                    )
                    # If the buyer has this kind of asset, then add to it; 
                    # otherwise, create a new entry
                    if buyer_stock is None:
                        self.session.add(
                            Asset(owner_id=buyer.user_id,
                                  asset_symbol=transaction.security_symbol,
                                  asset_amount=transaction.size))
                    else:
                        buyer_stock.asset_amount += transaction.size
                    # Remove cash from buyer
                    buyer_cash = self.session.query(Asset).get(
                        (buyer.user_id, "_CASH")
                    )
                    buyer_cash.asset_amount -= cash_volume
                    self.session.commit()

                    # Update the company's market price
                    company = self.session.query(Company).get(
                        transaction.security_symbol)
                    company.market_price = transaction.price
                    self.session.commit()
        
        if not self.ignore_user_logic:
            # If the incoming order is a selling order that is not 
            # entirely fulfilled, and whose remaining part is cancelled, 
            # then return the assets back to the seller
            if match_result.incoming_remain is not None \
                and (match_result.incoming_remain.cancelled_dttm is not None) \
                and (match_result.incoming_remain.side == "ask"):
                source_asset = self.session.query(Asset).get(
                    (match_result.incoming_remain.owner_id, 
                     match_result.incoming_remain.security_symbol)
                )
                refund_size = match_result.incoming_remain.size
                print(f"Refunding {refund_size} shares")
                source_asset.asset_amount += refund_size
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
            mr.incoming_remain.active = mr.incoming.active = True
            print(mr.incoming.active, mr.incoming_remain.active)
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
