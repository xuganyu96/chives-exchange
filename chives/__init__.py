from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chives.models import Base, Order, Transaction

engine = create_engine("sqlite:///:memory:", echo=False)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
