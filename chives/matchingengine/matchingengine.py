import datetime as dt
import logging
import os
import socket
import sys
import time
import typing as ty

import pika
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy.orm import sessionmaker, Session

from chives.models import (
    Base, Order, Transaction, Asset, User, Company, MatchingEngineLog)


# I am not adding file handler because at deployment, I will use an orchestrator 
# to log console output to a file
logger = logging.getLogger("chives.matchingengine")
logger.setLevel(logging.INFO)
chandle = logging.StreamHandler()
chandle.setLevel(logging.INFO)
formatter = logging.Formatter(
    '[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s')
chandle.setFormatter(formatter)
logger.addHandler(chandle)


class OrderNotFoundError(KeyError):
    """The exception to raise when the orderbook instance is asked to retrieve 
    an order that does not exist in self.active_orders
    """
    pass


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
    heartbeat_finish_msg = "Heartbeat finished"

    def __init__(self, me_sql_engine: SQLEngine,
                       ignore_user_logic: bool = False,
                       hostname: str = None):
        """Initialize the matching engine by instantiating the order book and 
        creating a engine-bound session

        :param me_sql_engine: The engine for connecting to the main database
        :type me_sql_engine: SQLEngine
        :param ignore_user_logic: if True, the matching engine will not modify 
        user assets after transactions are committed. Defaults to False
        :type ignore_user_logic: bool
        :param hostname: if a hostname is specified, use the specified hostname 
        otherwise, use socket.gethostname(), defaults to None
        :type hostname: str, optional
        """
        Session = sessionmaker(bind=me_sql_engine, autoflush=False)
        self.session = Session()
        self.ignore_user_logic = ignore_user_logic
        self.hostname = hostname if hostname else socket.gethostname()
        self.pid = os.getpid()
    
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
        security symbol, that are on the opposite sides, that do not come from 
        the same owner, and that offer better price than the incoming order, 
        if the incoming order has a target price

        :param incoming: the incoming order
        :type incoming: Order
        :return: A list of candidate orders
        :rtype: ty.List[Order]
        """
        candidates: ty.List[Order] = []
        cond = (Order.security_symbol == incoming.security_symbol) \
            & (Order.active == True)
        if incoming.owner_id:
            cond = cond & (Order.owner_id != incoming.owner_id)
        best_price = None
        if incoming.side == "bid":
            cond = cond & (Order.side == "ask")
            if incoming.price:
                cond = cond & (Order.price <= incoming.price)
            best_price = Order.price.asc()
        else:
            cond = cond & (Order.side == "bid")
            if incoming.price:
                cond = cond & (Order.price >= incoming.price)
            best_price = Order.price.desc()
        
        return self.session.query(Order).filter(cond).order_by(
            best_price, Order.create_dttm.desc()).all()

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
                    logger.debug(
                        f"AON resting order {candidate} rejected {incoming}")
                    return None
            else:
                # the transaction price will always be the candidate's 
                # price since by prior filtering, the candidate will 
                # always have the better pricing

                transaction: Transaction = Transaction(
                    security_symbol=ask.security_symbol,
                    size=transaction_size,
                    price=candidate.price,
                    ask_id=ask.order_id,
                    bid_id=bid.order_id,
                    aggressor_order_id=incoming.order_id,
                    resting_order_id=candidate.order_id
                )

                return transaction
    
    def exchange_user_asset(self, transaction: Transaction):
        """Given a transaction, find the parties involved in the transaction, 
        then perform the exchange of cash for stocks as reflected on the assets
        table

        :param transaction: [description]
        :type transaction: Transaction
        """
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
        self.session.merge(seller_cash)

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
            self.session.merge(buyer_stock)
        # Remove cash from buyer
        buyer_cash = self.session.query(Asset).get(
            (buyer.user_id, "_CASH")
        )
        buyer_cash.asset_amount -= cash_volume
        self.session.merge(buyer_cash)

    def update_market_price(self, transaction: Transaction):
        """Given a transaction object, find the company that this transaction 
        is trading on, then update the company's market price with the 
        transaction price

        :param transaction: [description]
        :type transaction: Transaction
        """
        # Update the company's market price
        company = self.session.query(Company).get(
            transaction.security_symbol)
        company.market_price = transaction.price
        self.session.merge(company)

    def refund_cancelled_remains(self, match_result: MatchResult):
        """If the incoming order is a selling order that is not entirely 
        fulfilled, and whose remaining part is cancelled, then return the 
        remaining part's assets back to the seller

        :param match_result: [description]
        :type match_result: MatchResult
        """
        if (match_result.incoming.side == "ask") \
            and match_result.incoming_remain is not None \
            and (match_result.incoming_remain.cancelled_dttm is not None):
            owner_id = match_result.incoming_remain.owner_id
            symbol = match_result.incoming_remain.security_symbol
            source_asset = self.session.query(Asset).get((owner_id, symbol))
            refund_size = match_result.incoming_remain.size
            logger.debug(f"Refunding {refund_size} shares")
            source_asset.asset_amount += refund_size
            self.session.merge(source_asset)

    def process_match_result(self, match_result: MatchResult):
        """Write changes described by the match result into the database:
        1.  incoming_order needs to be merged because it might be cancelled 
            or be made active
        2.  incoming_remain, if distinct from incoming_order and not None, 
            needs to be added into the database as a new order
        3.  A number of resting orders need to be deactivated because they 
            matched with the aggressor order and produced transaction
        4.  If there is a sub-order of a resting order, then it needs to be 
            added as a new order
        5.  For each transaction, add it into the database. 
            If user logic is not to be ignored, then 
            *   call exchange_user_asset to execute with the exchange of 
                assets induced by said transaction
            *   call update_market_price to update a company's stock's market
                price
        6.  If user logic is not to be ignored, then refund unfulfilled remains 
            of the selling order back to the user appropriately

        :param match_result: [description]
        :type match_result: MatchResult
        """
        self.session.merge(match_result.incoming)
        
        if match_result.incoming_remain is not match_result.incoming\
            and match_result.incoming_remain is not None:
            self.session.add(match_result.incoming_remain)
        
        if len(match_result.deactivated) > 0:
            for deactivated in match_result.deactivated:
                main_entry = self.session.query(Order).get(deactivated)
                main_entry.active = False 

        if match_result.reactivated is not None:
            self.session.add(match_result.reactivated)

        if len(match_result.transactions) > 0:
            for transaction in match_result.transactions:
                self.session.add(transaction)
                if not self.ignore_user_logic:
                    self.exchange_user_asset(transaction)
                    self.update_market_price(transaction)
        
        if not self.ignore_user_logic:
            self.refund_cancelled_remains(match_result)
    
    def _heartbeat(self, incoming: Order):
        """Register the incoming order into the main database, run it against 
        self.match, then commit the changes to main database and/or the 
        orderbook database

        :param incoming: the incoming order
        :type incoming: Order
        """
        logger.debug("Starting new heartbeat")
        self.session.close(); time.sleep(0.01)

        # The self.match method does not commit any actual changes to any 
        # database. Instead, it returns the set of changes that need to be 
        # committed.
        match_result: MatchResult = self.match(incoming)
        self.process_match_result(match_result)
        
        self.log_to_sql(msg=self.heartbeat_finish_msg)
        # This is the only commit that will happen for each heartbeat
        self.session.commit()

    def heartbeat(self, incoming: Order):
        try:
            logger.info(f"Trying to heartbeat {incoming}")
            self._heartbeat(incoming)
            logger.info(f"Heartbeated {incoming}")
        except Exception as e:
            logger.error(f"Commit failed: {e}")
            self.session.rollback()
            self.heartbeat(incoming)

    def match(self, incoming: Order) -> MatchResult:
        """The specific logic is recorded in the module README.

        :param incoming: [description]
        :type incoming: Order
        :return: [description]
        :rtype: MatchResult
        """
        mr = MatchResult()
        incoming.remaining_size = incoming.size 
        candidates: ty.List[Order] = self.get_candidates(incoming)
        logger.debug(f"Found {len(candidates)} resting orders as candidates")

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
                    logger.debug(f"{incoming} matches {candidate}: {transaction}")
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
            logger.debug(f"No trade proposed; incoming order's remain is itself")
            mr.incoming_remain = mr.incoming
            mr.incoming_remain.active = mr.incoming.active = True
        elif incoming.remaining_size > 0:
            logger.debug(f"Incoming order partially fulfilled; creating suborder")
            mr.incoming_remain = incoming.create_suborder()
            mr.incoming_remain.active = True
        else:
            logger.debug(f"Incoming order completely fulfilled")
            mr.incoming_remain = None

        # Respect the AON and IOC policy
        if incoming.all_or_none and incoming.remaining_size > 0:
            logger.debug(f"Incoming order is all-or-none and less than completely fulfilled")
            mr.incoming_remain = mr.incoming
            mr.incoming_remain.active = True
            mr.transactions = []
            # There is no need to refresh the candidate since each match() 
            # reads a fresh record from the database, which means the mutations 
            # in one match cycle does not persist to the next
            mr.deactivated = []
            mr.reactivated = None
        if incoming.immediate_or_cancel and (mr.incoming_remain is not None):
            logger.debug(f"Incoming order is immediate-or-cancel and has non-trivial remains")
            mr.incoming_remain.cancelled_dttm = dt.datetime.utcnow()
            mr.incoming_remain.active = False
        
        return mr

    def log_to_sql(self, msg: str, ext_ref: str = None, ext_ref_id: int = None):
        """Add a log message to the me_logs table

        :param msg: the message; if the message is longer than 1024 characters, 
        then it will be truncated
        :type msg: str
        :param ext_ref: table name of an external record, defaults to None
        :type ext_ref: str, optional
        :param ext_ref_id: id of the external record, defaults to None
        :type ext_ref_id: int, optional
        """
        msg = msg[:1024]
        self.session.add(MatchingEngineLog(
            hostname=self.hostname,
            pid=self.pid,
            log_msg=msg,
            ext_ref=ext_ref,
            ext_ref_id=ext_ref_id
        ))


def start_engine(queue_host: str, sql_engine: SQLEngine, dry_run: bool = False):
    """Initialize a RabbitMQ connection and a matching engine instance, then 
    start listening in for incoming order

    :param queue_host: hostname of the RabbitMQ server
    :type queue_host: str
    :param sql_engine: an SQLAlchemy engine that the matching engine uses to 
    construct the ORM session
    :type sql_engine: SQLEngine
    :param dry_run: if True, the matching engine will not heartbeat upon 
    receiving the incoming message, defaults to False
    :type dry_run: bool, optional
    """
    logger.info("Starting matching engine")

    conn = pika.BlockingConnection(pika.ConnectionParameters(host=queue_host))
    ch = conn.channel()
    ch.queue_declare(queue="incoming_order")
    logger.info("Connected to RabbitMQ")
    
    me = MatchingEngine(sql_engine)
    logger.info(f"Matching engine started at {me.hostname} with pid {me.pid}")

    def msg_callback(ch, method, properties, body):
        logger.info("Received %r" % body)
        if not dry_run:
            me.heartbeat(Order.from_json(body))
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    # Tells RabbitMQ not to give more than one message at a time;
    # do not dispatch a new message to a worker until it has processed and 
    # acknowledged the previous one
    ch.basic_qos(prefetch_count=1) 
    ch.basic_consume(queue="incoming_order", 
                     on_message_callback=msg_callback)
    logger.info("Listening for incoming order")
    ch.start_consuming()            
