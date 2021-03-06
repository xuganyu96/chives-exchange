import datetime as dt
import json
import random
import os
import time

from sqlalchemy import create_engine
import pika
from werkzeug.security import generate_password_hash 

from chives.db import SQLALCHEMY_URI
from chives.models.models import Order, Transaction, Asset, User, Company, Base
from chives.matchingengine.matchingengine import MatchingEngine

sql_engine = create_engine(SQLALCHEMY_URI, echo=False)
me = MatchingEngine(sql_engine)

def inject_asset(user_id, 
        asset_symbol="AAPL", asset_amount=10, session=me.session):
    """Given a user_id, insert a record of asset for this user, then return 
    the Asset object

    :param user_id: [description]
    :type user_id: [type]
    """
    existing_asset = session.query(Asset).get((user_id, asset_symbol))
    if existing_asset is None:
        session.add(Asset(owner_id=user_id, 
            asset_symbol=asset_symbol, asset_amount=asset_amount))
    else:
        existing_asset.asset_amount += asset_amount
    session.commit()

    return session.query(Asset).get((user_id, asset_symbol))

def inject_user(username: str, 
        raw_password: str="password", session=me.session):
    """Given a username and an optional raw_password, create a new user, add 
    it to the database, and return the user object

    :param username: [description]
    :type username: str
    :param raw_password: [description], defaults to "password"
    :type raw_password: str, optional
    """
    user = session.query(User).filter(User.username == username).first()
    if not user:  
        new_user = User(username=username, 
                        password_hash=generate_password_hash(raw_password))
        session.add(new_user)
        session.commit()
        return new_user
    else:
        return user

def simulate_trading(nrounds: int, symbol: str, matching_engine: MatchingEngine,
        start_dttm = dt.datetime(2020, 1, 1),
        end_dttm = dt.datetime.utcnow()):
    """Create 2 users: buyer and seller; create 1 company
    For each round:
    * Seller submits an ask of random size with random price
    * Buyer submits a bid of equal size but at market price
    
    At the and, query all transactions from this simulation session, and 
    assign them uniformly random datetimes generated between start and end dttm
    """
    seller = inject_user("seller", session=matching_engine.session)
    buyer = inject_user("buyer", session=matching_engine.session)
    inject_asset(seller.user_id, "_CASH", 10000000)
    inject_asset(buyer.user_id, "_CASH", 10000000)

    if not matching_engine.session.query(Company).get(symbol):
        company = Company(
            symbol=symbol,
            name=symbol,
            initial_value=10000,
            initial_size=10,
            founder_id=seller.user_id,
            market_price=10000/10
        )
        matching_engine.session.add(company)
        matching_engine.session.commit()
    
    session_order_ids = []
    for r in range(nrounds):
        random_size = random.randint(1, 100)
        random_price = random.uniform(10, 100)
        injected_asset = inject_asset(seller.user_id, symbol, random_size)
        injected_asset.asset_amount -= random_size
        matching_engine.session.commit()
        ask = Order(
            security_symbol=symbol,
            side="ask",
            size=random_size,
            price=random_price,
            owner_id=seller.user_id
        )
        bid = Order(
            security_symbol=symbol,
            side="bid",
            size=random_size,
            price=None,
            owner_id=buyer.user_id
        )
        matching_engine.heartbeat(ask)
        matching_engine.heartbeat(bid)
        session_order_ids.append(ask.order_id)
        session_order_ids.append(bid.order_id)
    
    # It is possible that this method is run repeatedly; to make sure that each 
    # method call only modifies the transact_dttm of this method calls' 
    # transactions, query by the ask/bid id
    is_in_session = Transaction.ask_id.in_(session_order_ids) \
        | Transaction.bid_id.in_(session_order_ids)
    sort_key = Transaction.transact_dttm.asc()
    transactions = matching_engine.session.query(
        Transaction).filter(is_in_session).order_by(sort_key).all()
    
    start_ts = start_dttm.timestamp()
    end_ts = end_dttm.timestamp()
    random_dttm = [
        dt.datetime.fromtimestamp(random.uniform(start_ts, end_ts))
        for i in range(len(transactions))]
    # the transcations are sorted by descending datetimes, so the random dttms 
    # are sorted in descending order, too
    random_dttm.sort()
    
    for i, t in enumerate(transactions):
        t.transact_dttm = random_dttm[i]
    matching_engine.session.commit()

if __name__ == "__main__":
    print("Removing old data")
    os.remove("/tmp/chives.sqlite")
    Base.metadata.create_all(sql_engine)
    now = dt.datetime.utcnow()

    for symbol in ["FB", "GOOGL", "AAPL", "MSFT", "NTLX", "TSLA", "AMZN"]:
        print(f"Simulating trades for {symbol}")
        start = time.time()
        for start_dttm, end_dttm in [
            # The earlier transactions should have the 
            (now - dt.timedelta(days=365*5), now - dt.timedelta(days=365)), # between -5 years and -1 year
            (now - dt.timedelta(days=365), now - dt.timedelta(days=30)), # between -1 year and -30 days
            (now - dt.timedelta(days=30), now - dt.timedelta(days=1)), # between -30 and -1 day
            (now - dt.timedelta(days=1), now), # -1 and 0 days
        ]:
            print(f"Simulating 1000 trades between {start_dttm} and {end_dttm}")
            simulate_trading(1000, symbol, me, start_dttm, end_dttm)
            rtime = time.time() - start 
        print(f"Finished in {rtime:.2f} seconds")

    