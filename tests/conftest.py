"""Common fixtures that can shared in all test cases
"""
import os
import typing as ty

from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy import create_engine
import pytest 

from chives.models import Order, Transaction
from chives.models import Base
    
@pytest.fixture 
def sql_engine() -> SQLEngine:
    """Create a SQLite database in the /tmp directory, yield the connection,
    then destroy it by deleting the database file

    :return: A SQLAlchemy engine
    :rtype: SQLEngine
    """
    engine = create_engine("sqlite:////tmp/sqlite.db", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    os.remove("/tmp/sqlite.db")