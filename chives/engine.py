from contextlib import contextmanager
import datetime as dt
import typing as ty

from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy.orm import sessionmaker

from chives.models import Order, Transaction
from chives import Session


class OrderNotFoundError(KeyError):
    """The exception to raise when the orderbook instance is asked to retrieve 
    an order that does not exist in self.active_orders
    """
    pass


class OrderBook:
    """
    Abstract of the limit order book that keeps track of active orders. 
    Instances of this class should be unaware of any matching activities, 
    nor should it have any interaction with the database.
    """

    def __init__(self, security_symbol: str):
        """Initialize a dictionary that contains all active orders with 
        self.active_orders. This dictionary maps order_id (as an integer) to 
        the Order object

        :param security_symbol: the symbol of the security being traded
        :type security_symbol: str
        """
        self.security_symbol = security_symbol
        self.active_orders: ty.Dict[int, Order] = dict()

    def get_order(self, order_id: int) -> Order:
        """Read an order by its order_id

        :param order_id: ID of the order to be obtained
        :type order_id: int
        :raises OrderNotFoundError: If the order_id has no match, raise it
        :return: The order
        :rtype: Order
        """
        if order_id in self.active_orders:
            return self.active_orders[order_id]
        else:
            raise OrderNotFoundError(f"Order ID {order_id} is not registered")

    def get_orders(self, cond: ty.Callable[[Order], bool]) -> ty.List[Order]:
        """Get a list of qualified orders

        :param cond: Python callable that takes an order and return a boolean
        :type cond: ty.Callable[[Order], bool]
        :return: a list of Order for which cond evals to True, might return 
        empty list if nothing matches
        :rtype: ty.List[Order]
        """
        return [order for id, order in self.active_orders.items() 
                    if cond(order)]
    
    def get_candidates(self, incoming: Order, 
                             sort: bool = True) -> ty.List[Order]:
        """Given an incoming order, return all active orders that are on the 
        opposite sides, and that offer better price than the incoming order if 
        the incoming order has a target price

        :param incoming: the incoming order
        :type incoming: Order
        :param sort: return the list with its content sorted from best offer 
        to worst offer, defaults to True
        :type sort: bool, optional
        :return: a list of Order candidate orders, if there is no match, return 
        an empty list
        :rtype: ty.List[Order]
        """
        candidates: ty.List[Order] = []
        if incoming.side == 'bid':
            candidates = self.get_orders(lambda order: order.side == 'ask')
            if incoming.price:
                candidates = self.get_orders(
                    lambda order: (order.side == 'ask') \
                                    and (order.price <= incoming.price)
                )
            if sort:
                candidates.sort(key=lambda o: o.price)
        else:
            candidates = self.get_orders(lambda order: order.side == 'bid')
            if incoming.price:
                candidates = self.get_orders(
                    lambda order: (order.side == 'bid') \
                                    and (order.price >= incoming.price)
                )
            if sort:
                candidates.sort(key=lambda o: -o.price)
        return candidates

    def register(self, order: Order):
        """Add an order to active_orders

        :param order: The order to be added
        :type order: Order
        """
        self.active_orders[order.order_id] = order
    
    def deregister(self, order_id: int) -> Order:
        """Remove an order from active_orders

        :param order_id: the id of the order to be removed
        :type order_id: int
        :raises OrderNotFoundError: If ther is no match, raise this error
        :return: The order that was removed
        :rtype: Order
        """
        if order_id in self.active_orders:
            return self.active_orders.pop(order_id)
        else:
            raise OrderNotFoundError(f"Order ID {order_id} is not found")


class MatchingEngine:
    """
    Abstraction of the matching engine with the following core components:
    -   interface with the order queue
    -   interface with the database, including the ORM session
    -   orderbook
    -   match cycle
    """
    def __init__(self, security_symbol: str, sql_engine: SQLEngine):
        """Initialize the matching engine

        :param security_symbol: the symbol of the security that this match 
        engine operates with
        :type security_symbol: str
        :param sql_engine: A SQLAlchemy engine object that will be used to 
        create ORM sessions
        :type sql_engine: sqlalchemy.engine.Engine
        """
        self.security_symbol = security_symbol 
        self.order_book = OrderBook(security_symbol)
        self.order_queue_client = None # TODO: This is for a future feature
        
        # Since session does not maintain an active connection all the time, 
        # it is okay to not use a context manager with session
        Session = sessionmaker(bind=sql_engine)
        self.session = Session()

    def heartbeat(self, debug: bool = False, **kwargs):
        """The core match cycle logic

        :param debug: If true, use an externally passed in order instead of 
        polling from the order queue, defaults to False
        :type debug: bool, optional
        """
        incoming: Order = None
        if debug:
            incoming = kwargs['incoming']
        else:
            incoming: Order = self.order_queue_client.poll()
        self.session.add(incoming)
        self.session.commit()

        updated_orders, transactions, new_active_orders = self.match(incoming)

        # It is possible that new active_order does not yet have an order_id, 
        # so it needs to go through the commit first before being registered
        for new_active_order in new_active_orders:
            # .merge method does not modify the input object but returns the
            # merged object
            new_active_order = self.session.merge(new_active_order)
            self.session.commit()
            self.order_book.register(new_active_order)

        for object_mapping in updated_orders + transactions:
            self.session.merge(object_mapping)
        self.session.commit()
    
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
        
    def match(self, incoming: Order) -> ty.Tuple[ty.List[Order], 
                                                 ty.List[Transaction],
                                                 ty.List[Order]]:
        """Execute the matching algorithm that matches the incoming order with 
        the active orders in the order book. Changes to the order book's 
        active order registry will happen with this method, and those changes 
        are entirely operating within the RAM. Changes to the database, such 
        as updates to existing orders and insertion of new orders/transactions,
        will be returned as ORM instances to be committed outside this method, 
        but within the heartbeat method.

        :param incoming: the incoming order
        :type incoming: chives.models.Order
        :return: A tuple of 3: a list of existing Order objects to be updated 
        into the databases, a list of new Transaction objects to be added 
        into the databases, and a list of new active orders to be added into 
        the database.
        :rtype: ty.Tuple[ty.List[Order], ty.List[Transaction]]
        """
        order_updates: ty.List[Order] = []
        transactions: ty.List[Transaction] = []
        new_active_orders: ty.List[Order] = []
        
        candidates = self.order_book.get_candidates(incoming)
        
        # Note that at this moment, every candidate has an order_id, because 
        # every candidate was once an incoming order, and each incoming order 
        # is guaranteed to be committed into the database by the end of its
        # match cycle.
        #
        # We need to keep track of the remaining size of the incoming order, 
        # but I don't want to mutate existing column attributes of the 
        # incoming_order. Instead, we can attach a new attribute to the 
        # incoming object
        incoming.remaining_size = incoming.size
        for candidate in candidates:
            candidate.remaining_size = candidate.size
            # "remaining_size" will not be mutated within self.propose_trade
            transaction: Transaction = self.propose_trade(incoming, candidate)
            if transaction is not None:
                incoming.remaining_size -= transaction.size 
                candidate.remaining_size -= transaction.size
                transactions.append(transaction)

        # Create the appropriate suborder for the incoming order and mutate
        # the incoming order according to its order types; by the end of this 
        # section we should have an remaining and an incoming
        remaining = incoming.create_suborder()
        if len(transactions) == 0:
            # If there is no transactions in the first place, then remaining 
            # is exactly incoming:
            remaining = incoming
        if incoming.all_or_none and incoming.remaining_size > 0:
            # If the incoming order is all-or-none and is not fully fulfilled, 
            # then no trade will be made, and the remaining order is the 
            # incoming order itself.
            remaining = incoming
            transactions = []
            incoming.remaining_size = incoming.size 
            for candidate in candidates:
                candidate.remaining_size = candidate.size
        if incoming.immediate_or_cancel and incoming.remaining_size > 0:
            # If the incoming order is immediate-or-cancel and is not fully 
            # fulfilled, then the remains will be cancelled. Note that if 
            # the incoming also happens to be all-or-none, then "remaining" 
            # will point to "incoming", so the incoming order itself becomes 
            # cancelled
            remaining.cancelled_dttm = dt.datetime.utcnow()
        if remaining.cancelled_dttm is None and remaining.size > 0:
            # If the remaining order is not cancelled yet, it is active. Add 
            # it to the active order registry
            remaining.active = True 
            new_active_orders.append(remaining)
        
        # Add incoming and remaining to order_updates. It is okay if incoming
        # and remaining are the same thing, since SQLAlchemy can handle 
        # merging the same ORM instance twice
        order_updates.append(incoming)
        if remaining.size > 0:
            order_updates.append(remaining)
        
        # Clean up the candidates
        for candidate in candidates:
            if candidate.remaining_size <= 0:
                # If the active order is fully fulfilled, then it is no longer 
                # active
                candidate.active = False
                self.order_book.deregister(candidate.order_id)
                order_updates.append(candidate)
            elif candidate.remaining_size < candidate.size:
                # If the active order is partially fulfilled, then create an 
                # active sub-order, deregister the original, and register 
                # the sub-order
                candidate.active = False 
                candidate_remain = candidate.create_suborder()
                candidate_remain.active = True
                self.order_book.deregister(candidate.order_id)
                new_active_orders.append(candidate_remain)
                order_updates.append(candidate)
            else:
                # If the active order is not touched, then do nothing
                pass
        return order_updates, transactions, new_active_orders
