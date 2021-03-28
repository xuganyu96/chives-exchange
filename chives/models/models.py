import datetime as dt

from sqlalchemy import (Column, String, Integer, Time, DateTime)
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    email = Column(String(256), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    name = Column(String(256), nullable=True)
    create_dttm = Column(DateTime, default=dt.datetime.utcnow)
    close_dttm = Column(DateTime, default=dt.datetime.utcnow)

    def __str__(self) -> str:
        return f"<Account id={self.id} email={self.email}>"
    
    def __repr__(self) -> str:
        return self.__str__()
