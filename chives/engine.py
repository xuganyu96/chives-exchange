import datetime as dt
import typing as ty

from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy.orm import sessionmaker

from chives.models import Order, Transaction
from chives import session, Session


class OrderNotFoundError(KeyError):
    """
    The exception to raise when the orderbook instance is asked to retrieve an order that does not
    exist in self.active_orders
    """
    pass


class MatchCycle:
    """
    Abstraction of the union of incoming order, candidate active orders, and transactions, denoted 
    by "state of the match cycle". It presents itself as a clean slate with predefined structure 
    and mutates its attributes as the match cycle progresses, then commits the changes to database 
    where necessary before returning itself to the clean slate to prepare for a second match cycle.

    Instances of MatchCycle should be unaware of anything in the active order registry. This class 
    is solely responsible for holding onto and providing the static components of a match cycle
    """
    def __init__(self):
        """
        A match cycle has three components: incoming order, candidate active orders, transactions
        """
        self.incoming: Order = None 
        self.candidates = []
        self.matched_candidates: ty.List[Order] = []
        self.transactions: ty.List[Order] = []
    
    def __enter__(self):
        """
        :return: self
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.incoming = None 
        self.candidates = []
        self.matched_candidates = []
        self.transactions = []

    def register_incoming(self, incoming: Order):
        """
        :param incoming: the incoming order instance 
        :return: None. This method will commit the incoming order instance to the database, then 
        assign it to self.incoming
        """
        session.add(incoming)
        session.commit()
        self.incoming = incoming


class OrderBook:
    """
    Abstract of the limit order book that keeps track of active orders. Instances of this class 
    should be unaware of any matching activities, nor should it have any interaction with the 
    database.
    """

    def __init__(self, security_symbol: str):
        """
        Initialize a dictionary that contains all active orders with self.active_orders.
        This dictionary maps order_id (as an integer) to the Order object
        """
        self.security_symbol = security_symbol
        self.active_orders: ty.Dict[int, Order] = dict()
        self.cycle_state = MatchCycle()

    def get_order(self, order_id: int) -> Order:
        """
        :param order_id: the order ID
        :return: an Order object that has identical order_id; if there is no order, let the 
        dictionary object raise the KeyError exception
        """
        if order_id in self.active_orders:
            return self.active_orders[order_id]
        else:
            raise OrderNotFoundError(f"Order ID {order_id} is not registered in order book")

    def get_orders(self, cond: ty.Callable[[Order], bool]) -> ty.List[Order]:
        """
        :param cond: a Python callable that takes an Order object and returns a boolean
        :return: a list of Orders for which cond(order) evals to True. Might return empty list
        """
        return [order for id, order in self.active_orders.items() if cond(order)]
    
    def register(self, order: Order):
        """
        :param order: the order to be added into the active_orders dictionary
        :return: None
        """
        self.active_orders[order.id] = order
    
    def deregister(self, order_id: int) -> Order:
        """
        :param order_id: an integer that is the order ID of the order to be removed from order book
        :return: the Order object removed. If there is no matching order_id, then let the dictionary
        object raise the KeyError exception
        """
        if order_id in self.active_orders:
            return self.active_orders.pop(order_id)
        else:
            raise OrderNotFoundError(f"Order ID {order_id} is not registered in order book")


class MatchingEngine:
    """
    Abstraction of the matching engine with the following core components:
    -   interface with the order queue
    -   interface with the database， including the ORM session
    -   orderbook
    -   match cycle
    """
    def __init__(self, security_symbol: str, sql_engine: SQLEngine):
        """Initialize the matching engine

        :param security_symbol: [description]
        :type security_symbol: str
        :param sql_engine: [description]
        :type sql_engine: SQLEngine
        """
        self.security_symbol = security_symbol 
        self.order_book = OrderBook(security=security_symbol)
        self.order_queue_client = None # TODO: This is for a next issue
        self.Session = sessionmaker(bind=sql_engine)

    def heartbeat(self):
        """The main cycle of operation that goes: get an incoming order, generate a match cycle, 
        commit changes to database.
        """
        incoming: Order = self.order_queue_client.poll()
        updated_orders, transactions = self.match(incoming)
        
        with self.Session() as session:
            for object_mapping in updated_orders + transactions:
                session.merge(object_mapping)
            session.commit()


    


# def get_candidates(self, sort: bool = True) -> ty.List[Order]:
# """
# :param sort: if True, then the candidates will be sorted based on price. Specifically, if 
# the incoming order is a bid, then the candidates are sorted in ascending prices; otherwise,
# the candidates are sorted in descending prices
# :return: a list of Order instances from self.active_orders that satisfy the following 
# conditions: 
# 1.  they are from the oppposite side of the incoming order
# 2.  if the incoming order has a target price, then the target price of the active order 
# must be equal to or better than the incoming's target price
# """
# candidates = []
# incoming = self.cycle_state.incoming
# if incoming.side == 'bid':
#     candidates = self.get_orders(lambda order: order.side == 'ask')
#     if incoming.price:
#         candidates = self.get_orders(
#             lambda order: (order.side == 'ask') and (order.price <= incoming.price)
#         )
#     candidates.sort(key=lambda o: o.price)
# else:
#     candidates = self.get_orders(lambda order: order.side == 'bid')
#     if incoming.price:
#         candidates = self.get_orders(
#             lambda order: (order.side == 'bid') and (order.price >= incoming.price)
#         )
#     candidates.sort(key=lambda o: -o.price)
# return candidates

# def propose_trade(self, incoming: Order, active_order: Order):
# """
# :param incoming: the incoming order, possibly with reduced size through prior trade 
# proposals
# :param active_order: the active order to be matched against the incoming order
# :return: if the incoming order and the active order can match up in a trade, then create 
# the appropriate Transaction instance and retunr it. There are cases in which no trade can 
# be proposed, in which case None is returned
# """
# # Note that this method is no responsible for checking that the pair has opposite sides 
# # and intersecting target price
# ask = incoming if incoming.side == 'ask' else active_order
# bid = incoming if incoming.side == 'bid' else active_order 
# transaction_size = min(ask.size, bid.size)

# # If the active_order is all-or-none, and the transaction cannot fulfill the active_order,
# # then no trade is proposed, None is returned
# if active_order.all_or_none and transaction_size < active_order.size:
#     return None
# else:
#     # active_order always has an equal or better deal than the incoming order so we 
#     # always use the active_order's price
#     transaction = Transaction(
#         security=ask.security,
#         ask_id=ask.id,
#         bid_id=bid.id,
#         size=transaction_size,
#         price=active_order.price
#     )
#     return transaction

# def cleanup_incoming(self):
# """
# :param incoming: the incoming order, possibly mutated after all trade proposals were made
# :return: None. The method will run the incoming order through its policy types and apply 
# all-or-none and immediate-or-cancel appropriately. Finally, if there is remaining part of
# the order that is unfulfilled and not cancelled, it will be registered into the active 
# orders to be matched in later cycles.
# """
# incoming = self.cycle_state.incoming
# # Clean up the remaining portion of the incoming order 
# # TODO: write test cases for each of the following logical branches:
# #       1. incoming order is completely fulfilled, or partially fulfilled, or not fulfilled
# #       2. incoming order is all-or-none or not
# #       3. incoming order is immediate-or-cancel or not
# remaining = incoming.create_suborder()
# if len(self.cycle_state.transactions) == 0:
#     # No transactions was proposed, so the "remaining" is just the incoming itself
#     remaining = incoming
# if incoming.all_or_none and remaining.size > 0:
#     session.refresh(incoming)
#     remaining = incoming 
#     for candidate in self.cycle_state.matched_candidates:
#         session.refresh(candidate)
#     transactions = []
# if incoming.immediate_or_cancel and remaining.size > 0:
#     remaining.cancelled_dttm = dt.datetime.utcnow()
# if remaining.size > 0 and remaining.cancelled_dttm is None:
#     self.register(remaining)
# if remaining.size > 0:
#     # The remaining portion will become an active order
#     remaining.active = True
#     session.refresh(incoming)
#     session.add(remaining)
#     session.commit()

# def commit_trades(self):
# """
# :return: None.  The method will instead commit all the transactions to database, then 
# clean up the active orders, removing candidate matches that were fulfilled, and adding back
# partially fulfilled candidate orders
# """
# incoming = self.cycle_state.incoming
# # Commit the transactions and clean up the orderbook
# for transaction in self.cycle_state.transactions:
#     session.add(transaction)
#     session.commit()
#     # Use the transaction to find the matched candidate, then deregister that
#     # candidate from the active orders
#     matched_candidate_id = transaction.ask_id
#     if incoming.id == transaction.ask_id:
#         # If the incoming order is the ask, then the candidate must be the bid
#         matched_candidate_id = transaction.bid_id
    
#     matched_candidate = self.get_order(matched_candidate_id)
#     matched_candidate.active = False 
#     self.deregister(matched_candidate.id)
#     session.commit()
#     # If a matched candidate has remainings, then create a suborder and register it with 
#     # the active orders
#     if matched_candidate.size > 0:
#         remaining_matched_candidate = matched_candidate.create_suborder()
#         remaining_matched_candidate.active = True 
#         session.add(remaining_matched_candidate)
#         session.commit() 
#         self.register(remaining_matched_candidate)

# def match(self, incoming: Order):
# """
# Perform the matching actions, propose and validate transactions, then commit to database
# :param incoming: the incoming order
# :return: None. This method will perform one matching cycle in which the incoming order is
# matched with active orders, transactions are proposed where appropriate, and trades 
# executed and committed into database
# """
# with self.cycle_state: 
#     self.cycle_state.register_incoming(incoming)

#     # Get candidate matches
#     self.cycle_state.candidates = self.get_candidates(sort=True)
#     for candidate in self.cycle_state.candidates:
#         transaction = self.propose_trade(incoming, candidate)
#         if transaction is not None:
#             self.cycle_state.transactions.append(transaction)
#             self.cycle_state.matched_candidates.append(candidate)
#             incoming.size -= transaction.size
#             candidate.size -= transaction.size
#     self.cleanup_incoming()
#     self.commit_trades()