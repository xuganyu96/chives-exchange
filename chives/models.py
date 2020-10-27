from sqlalchemy import Column, Integer, String, Boolean, Float, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base

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
    cancelled_dttm = Column(TIMESTAMP)

    def __repr__(self):
        return f"<Order(id={self.id}, security={self.security}, side={self.side})>"

    def __str__(self):
        return self.__repr__()
