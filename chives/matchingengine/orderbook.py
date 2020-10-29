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

    def match(self, incoming_order: Order):
        """
        Perform the matching actions, propose and validate transactions, then commit to database
        :param incoming_order: the incoming order
        :return: None
        """
        pass
