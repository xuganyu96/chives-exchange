import datetime as dt
import typing as ty

from chives.models import Order, Transaction
from chives import session


class OrderNotFoundError(KeyError):
        pass


class OrderBook:
    """
    Abstraction of an order book that contains active limit orders that can be matched against 
    an incoming order
    """

    def __init__(self, security: str):
        """
        Initialize a dictionary that contains all active orders with self.active_orders.
        This dictionary maps order_id (as an integer) to the Order object
        """
        self.security = security
        self.active_orders: ty.Dict[int, Order] = dict()
        self.cycle_state = dict()

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
    
    def get_candidates(self, incoming: Order) -> ty.List[Order]:
        candidates = []
        if incoming.side == 'bid':
            candidates = self.get_orders(lambda order: order.side == 'ask')
            if incoming.price:
                candidates = self.get_orders(
                    lambda order: (order.side == 'ask') and (order.price <= incoming.price)
                )
        else:
            candidates = self.get_orders(lambda order: order.side == 'bid')
            if incoming.price:
                candidates = self.get_orders(
                    lambda order: (order.side == 'bid') and (order.price >= incoming.price)
                )
        return candidates

    def propose_trade(self, incoming: Order, active_order: Order):
        ask = incoming if incoming.side == 'ask' else active_order
        bid = incoming if incoming.side == 'bid' else active_order 
        transaction_size = min(ask.size, bid.size)
        
        # If the active_order is all-or-none, and the transaction cannot fulfill the active_order,
        # then no trade is proposed, None is returned
        if active_order.all_or_none and transaction_size < active_order.size:
            return None
        else:
            transaction = Transaction(
                security=ask.security,
                ask_id=ask.id,
                bid_id=bid.id,
                size=transaction_size,
                # active_order always has an equal or better deal than the incoming order so we 
                # always use the active_order's price
                price=active_order.price
            )
            return transaction
    
    def cleanup_incoming(self, incoming: Order):
        # Clean up the remaining portion of the incoming order 
        remaining = incoming.create_suborder()
        if len(self.cycle_state['transactions']) == 0:
            # No transactions was proposed, so the "remaining" is just the incoming itself
            remaining = incoming
        if incoming.all_or_none and remaining.size > 0:
            session.refresh(incoming)
            remaining = incoming 
            for candidate in self.cycle_state['matched_candidates']:
                session.refresh(candidate)
            transactions = []
        if incoming.immediate_or_cancel and remaining.size > 0:
            remaining.cancelled_dttm = dt.datetime.utcnow()
        if remaining.size > 0 and remaining.cancelled_dttm is None:
            self.register(remaining)
        if remaining.size > 0:
            # The remaining portion will become an active order
            remaining.active = True
            session.refresh(incoming)
            session.add(remaining)
            session.commit()
    
    def commit_trades(self, incoming: Order):
        # Commit the transactions and clean up the orderbook
        for transaction in self.cycle_state['transactions']:
            session.add(transaction)
            session.commit()
            # Use the transaction to find the matched candidate, then deregister that
            # candidate from the active orders
            matched_candidate_id = transaction.ask_id
            if incoming.id == transaction.ask_id:
                # If the incoming order is the ask, then the candidate must be the bid
                matched_candidate_id = transaction.bid_id
            
            matched_candidate = self.get_order(matched_candidate_id)
            matched_candidate.active = False 
            self.deregister(matched_candidate.id)
            session.commit()
            # If a matched candidate has remainings, then create a suborder and register it with 
            # the active orders
            if matched_candidate.size > 0:
                remaining_matched_candidate = matched_candidate.create_suborder()
                remaining_matched_candidate.active = True 
                session.add(remaining_matched_candidate)
                session.commit() 
                self.register(remaining_matched_candidate)

    def match(self, incoming: Order):
        """
        Perform the matching actions, propose and validate transactions, then commit to database
        :param incoming: the incoming order
        :return: None
        """
        session.add(incoming)
        session.commit()

        self.cycle_state['transactions']: ty.List[Transaction] = []

        # Get candidate matches
        candidates = self.get_candidates(incoming)
        candidates.sort(key=lambda order: order.price)
        self.cycle_state['matched_candidates'] = []
        for candidate in candidates:
            transaction = self.propose_trade(incoming, candidate)
            if transaction is not None:
                self.cycle_state['transactions'].append(transaction)
                self.cycle_state['matched_candidates'].append(candidate)
                incoming.size -= transaction.size
                candidate.size -= transaction.size
        
        self.cleanup_incoming(incoming)

        self.commit_trades(incoming)
        self.cycle_state = dict()
