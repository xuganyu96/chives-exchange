from sqlalchemy import create_engine
from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy.orm import sessionmaker

from chives.models import Base, Order


_DEFAULT_OB_ENGINE = create_engine("sqlite:///:memory:", echo=False)

class OrderBook:
    """Abstraction of a limit order books that maintains active orders
    """
    def __init__(self, security_symbol: str, 
                 sql_engine: SQLEngine = _DEFAULT_OB_ENGINE):
        """Upon instantiation, create the session object, and initialize the 
        database using the engine provided

        :param security_symbol: [description]
        :type security_symbol: str
        :param sql_engine: [description], defaults to _DEFAULT_OB_ENGINE
        :type sql_engine: SQLEngine, optional
        """
        self.security_symbol = security_symbol 
        Session = sessionmaker(bind=sql_engine)
        self.session = Session()

        # Create the table schemas if they don't exist; in addition, 
        # the order book is only concerned with orders, so there is no
        # need to create other tables
        Base.metadata.create_all(sql_engine, 
            [Base.metadata.tables[Order.__tablename__]], checkfirst=True)
