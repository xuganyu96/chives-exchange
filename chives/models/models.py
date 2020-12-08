import datetime as dt
import json

from flask_login import UserMixin
from sqlalchemy import (
    Column, Integer, String, Boolean, Float, DateTime, ForeignKey)
from sqlalchemy.orm import relationship

from chives.db import Base


class User(UserMixin, Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    username = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(120), nullable=False)

    assets = relationship(
        "Asset", back_populates="owner", 
        cascade="all, delete",
        # setting passive_deletes to True means that the deletion cascade is 
        # handled by the database via the "ON DELETE" declaration, instead by 
        # SQLAlchemy
        passive_deletes=True)
    orders = relationship(
        "Order", back_populates="owner", 
        cascade="all, delete",
        passive_deletes=True)
    companies = relationship(
        "Company", back_populates="founder", 
        cascade="all, delete",
        passive_deletes=True)

    def __str__(self):
        return f"<User user_id={self.user_id}, username={self.username}>"

    def __repr__(self):
        return self.__str__()
    
    def get_id(self):
        return self.user_id


class Asset(Base):
    __tablename__ = 'assets'

    owner_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"), 
                        primary_key=True)
    asset_symbol = Column(String(10), primary_key=True)
    asset_amount = Column(Float, nullable=False)

    owner = relationship("User", back_populates="assets")

    def __str__(self):
        attr_list = ", ".join([
            f"owner_id={self.owner_id}",
            f"symbol={self.asset_symbol}",
            f"amount={self.asset_amount}",
        ])
        return f"<User {attr_list}>"

    def __repr__(self):
        return self.__str__()


class Company(Base):
    """Abstracting the individual securities/companies.
    Initial value is the amount of cash put into the company by the founder.
    Market price is the price of a share of this company, which is determined 
    either at founding, or by the latest transaction on this company's stock
    """
    __tablename__ = "companies"

    symbol = Column(String(10), nullable=False, primary_key=True)
    name = Column(String(50), nullable=False)
    initial_value = Column(Float, nullable=False)
    initial_size = Column(Integer, nullable=False)
    founder_id = Column(Integer, ForeignKey('users.user_id', ondelete="SET NULL"))
    market_price = Column(Float, nullable=False)
    create_dttm = Column(DateTime, default=dt.datetime.utcnow)

    founder = relationship("User", back_populates="companies")

    def __str__(self):
        attr_list = ", ".join([
            f"symbol={self.symbol}",
            f"name={self.name}",
            f"founder_id={self.founder_id}",
            f"create_dttm={self.create_dttm}",
        ])
        return f"<User {attr_list}>"

    def __repr__(self):
        return self.__str__()


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
    owner_id = Column(Integer, ForeignKey('users.user_id', ondelete="CASCADE"))
    cancelled_dttm = Column(DateTime)
    create_dttm = Column(DateTime, default=dt.datetime.utcnow)

    owner = relationship("User", back_populates="orders")

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
            owner_id=self.owner_id,
            cancelled_dttm=self.cancelled_dttm,
            create_dttm=self.create_dttm
        )

    def copy(self):
        """Return an Order object with exactly the same set of attributes; 
        useful when synchronizing entries across two different ORM sessions

        :return: [description]
        :rtype: [type]
        """
        return Order(
            order_id=self.order_id,
            security_symbol=self.security_symbol,
            side=self.side,
            size=self.size,
            price=self.price,
            all_or_none=self.all_or_none,
            immediate_or_cancel=self.immediate_or_cancel,
            active=self.active,
            parent_order_id=self.parent_order_id,
            owner_id=self.owner_id,
            cancelled_dttm=self.cancelled_dttm,
            create_dttm=self.create_dttm
        )

    @property
    def json(self) -> str:
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
            'owner_id': self.owner_id,
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
        attr_list = ", ".join([
            f"id={self.order_id}",
            f"symbol={self.security_symbol}",
            f"side={self.side}",
            f"size={self.size}",
            f"price={self.price}",
            f"owner_id={self.owner_id}",
        ])
        return f"<Order({attr_list})>"

    def __str__(self):
        return self.__repr__()


class Transaction(Base):
    __tablename__ = 'transactions'

    transaction_id = Column(Integer, primary_key=True)
    security_symbol = Column(String(10), nullable=False)
    size = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    # With asks and bids, I am not going to define any relationships because 
    # the concept is strange: what is order.transactions? Is it all transactions 
    # that this order is involved in? Or is it specific to when this order is 
    # a ask vs a bid?
    ask_id = Column(Integer, 
        ForeignKey('orders.order_id', ondelete="CASCADE"), nullable=False)
    bid_id = Column(Integer, 
        ForeignKey('orders.order_id', ondelete="CASCADE"), nullable=False)
    aggressor_order_id = Column(Integer, 
        ForeignKey('orders.order_id', ondelete="CASCADE"), nullable=False)
    resting_order_id = Column(Integer,
        ForeignKey('orders.order_id', ondelete="CASCADE"), 
        nullable=False, unique=True)
    transact_dttm = Column(DateTime, nullable=False, default=dt.datetime.utcnow)

    def __repr__(self):
        attr_list = ", ".join([
            f"id={self.transaction_id}",
            f"time={self.transact_dttm}",
            f"price={self.price}",
            f"size={self.size}",
            f"ask_id={self.ask_id}",
            f"bid_id={self.bid_id}",
        ])
        return f"<Transaction({attr_list})>"

    def __str__(self):
        return self.__repr__()


class MatchingEngineLog(Base):
    """A database-side logging table for recording matching engine's activities:

    :param Base: [description]
    :type Base: [type]
    """
    __tablename__ = 'me_logs'

    log_id = Column(Integer, primary_key=True)
    hostname = Column(String(256), nullable=False)
    pid = Column(Integer, nullable=False)
    log_dttm = Column(DateTime, default=dt.datetime.utcnow, nullable=False)
    log_msg = Column(String(1024))
    ext_ref = Column(String(32))
    ext_ref_id = Column(Integer)
