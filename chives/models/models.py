import datetime as dt

from sqlalchemy import (Column, String, Integer, Time, DateTime)
from sqlalchemy.ext.declarative import declarative_base
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    email = Column(String(256), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    name = Column(String(256), nullable=True)
    create_dttm = Column(DateTime, default=dt.datetime.utcnow)
    close_dttm = Column(DateTime, default=dt.datetime.utcnow)

    @staticmethod 
    def hash_password(password) -> str:
        """Given a password, return the hash of a password using SHA256 
        """
        return generate_password_hash(password)

    def check_password_hash(self, password) -> bool:
        """Given a password, run werkzeug.check_password_hash against the hash
        stored within the database"""
        return check_password_hash(self.password_hash, password)


    def __str__(self) -> str:
        return f"<Account id={self.id} email={self.email}>"
    
    def __repr__(self) -> str:
        return self.__str__()
