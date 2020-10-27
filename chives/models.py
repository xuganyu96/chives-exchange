from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.functions import now as server_side_now

Base = declarative_base()


class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    security = Column(String(10), nullable=False)
    side = Column(String(3), nullable=False)
    size = Column(Integer, nullable=False)
    price = Column(Float)
    all_or_none = Column(Boolean, nullable=False, default=False)
    immediate_or_cancel = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, nullable=False, default=False)
    # good_util_cancelled = Column(Boolean, nullable=False) is out of scope
    cancelled_dttm = Column(DateTime)

    def __repr__(self):
        return f"<Order(id={self.id}, security={self.security}, side={self.side})>"

    def __str__(self):
        return self.__repr__()


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    security = Column(String(10), nullable=False)
    size = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    ask_id = Column(Integer, nullable=False) # TODO: Convert to foreign key later
    bid_id = Column(Integer, nullable=False) # TODO: Convert to foreign key later
    transact_dttm = Column(DateTime, nullable=False, default=server_side_now)

    def __repr__(self):
        return f"<Transaction(id={self.id} time={self.transact_dttm})>"

    def __str__(self):
        return self.__repr__()

