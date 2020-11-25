"""Common fixtures that can shared in all test cases
"""
import os
import tempfile
import typing as ty

from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy import create_engine
import pytest 

from chives.models import Order, Transaction
from chives.models import Base
    
@pytest.fixture(scope="function") 
def sql_engine() -> SQLEngine:
    """Create a SQLite database in the /tmp directory, yield the connection,
    then destroy it by deleting the database file

    :return: A SQLAlchemy engine
    :rtype: SQLEngine
    """
    file_descriptor, file_name = tempfile.mkstemp()
    engine = create_engine(f"sqlite:///{file_name}", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    # After finishing each test, close the connection to 
    os.close(file_descriptor)
    os.unlink(file_name)
