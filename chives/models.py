import datetime as dt
import json

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Order(Base):
    __tablename__ = 'orders'

    order_id = Column(Integer, primary_key=True)
    security_symbol = Column(String(10), nullable=False)
    side = Column(String(3), nullable=False)
    size = Column(Integer, nullable=False)
    # market orders and sub-orders of market orders do not have target price
    price = Column(Float)
    all_or_none = Column(Boolean, nullable=False, default=False)
    immediate_or_cancel = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=False)
    # good_util_cancelled = Column(Boolean, nullable=False) is out of scope
    parent_order_id = Column(Integer, unique=True)
    cancelled_dttm = Column(DateTime)

    # A numerical placeholder, not a part of the database schema
    remaining_size: int = 0

    def create_suborder(self):
        return Order(
            security_symbol=self.security_symbol,
            side=self.side,
            size=self.remaining_size,
            price=self.price,
            all_or_none=self.all_or_none,
            immediate_or_cancel=self.immediate_or_cancel,
            active=self.active,
            parent_order_id=self.order_id,
            cancelled_dttm=self.cancelled_dttm
        )

    def to_json(self) -> str:
        """Return a JSON string that captures a manually specified set of 
        instance attributes

        :return: the JSON string
        :rtype: str
        """
        return json.dumps({
            'order_id': self.order_id,
            'security_symbol': self.security_symbol,
            'side': self.side,
            'size': self.size,
            'price': self.price,
            'all_or_none': self.all_or_none,
            'immediate_or_cancel': self.immediate_or_cancel,
            'active': self.active,
            'parent_order_id': self.parent_order_id,
            'cancelled_dttm': self.cancelled_dttm
        })
    
    @classmethod
    def from_json(cls, jstring: str):
        """Given a JSON string, return an Order object. Given that this method 
        is defined under the Base model class, there is no way to bind the 
        object to any session, as the ID columns are just integers.
        It will be up to the external session management to recover the exact 
        mapping from the object to the database entry.

        :param jstring: a JSON string
        :type jstring: str
        :return: The Order object that is mapped from the object
        :rtype: Order
        """
        return cls(**json.loads(jstring))

    def __repr__(self):
        return f"<Order(id={self.order_id}, symbol={self.security_symbol}, side={self.side})>"

    def __str__(self):
        return self.__repr__()


class Transaction(Base):
    __tablename__ = 'transactions'

    transaction_id = Column(Integer, primary_key=True)
    security_symbol = Column(String(10), nullable=False)
    size = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    ask_id = Column(Integer, nullable=False) # TODO: Convert to foreign key later
    bid_id = Column(Integer, nullable=False) # TODO: Convert to foreign key later
    transact_dttm = Column(DateTime, nullable=False, default=dt.datetime.utcnow)

    def __repr__(self):
        return f"<Transaction(id={self.transaction_id} time={self.transact_dttm})>"

    def __str__(self):
        return self.__repr__()
