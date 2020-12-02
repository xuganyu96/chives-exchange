import os 
import random
import datetime as dt
import time

import pika
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from werkzeug.security import generate_password_hash

from chives.models import Base, User, Company, Asset, Order, Transaction


DEFAULT_SQLITE_PATH = "/tmp/benchmark.chives.sqlite"
DEFAULT_MYSQL_URI = "mysql+pymysql://chives_u:chives_password@localhost:3307/chives"

def remove_old_sqlite(filepath: str = DEFAULT_SQLITE_PATH):
    if os.path.isfile(filepath):
        os.remove(filepath)


def add_user(username: str, password: str, sql_session: Session) -> User:
    """Add a user with the username and password, then return the user object;
    if something goes wrong, let the commit() method raise exception

    :param username: [description]
    :type username: str
    :param password: [description]
    :type password: str
    :param sql_session: [description]
    :type sql_session: Session
    """
    new_user = User(
        username=username, password_hash=generate_password_hash(password))
    sql_session.add(new_user)
    sql_session.commit()

    return new_user


def add_company(symbol: str, founder_id: int, sql_session: Session) -> Company:
    """Add a new company with the specified symbol and founder_id

    :param symbol: [description]
    :type symbol: str
    :param founder_id: [description]
    :type founder_id: int
    :return: [description]
    :rtype: Company
    """
    new_company = Company(
        symbol=symbol,
        name=symbol,
        initial_value=10000,
        initial_size=10000,
        founder_id=founder_id,
        market_price=1
    )
    sql_session.add(new_company)
    sql_session.commit()

    return new_company


def inject_asset(user_id: int, symbol: str, amount: int, session: Session):
    """Given a user_id, insert a record of asset for this user, then return 
    the Asset object

    :param user_id: [description]
    :type user_id: [type]
    """
    existing_asset = session.query(Asset).get((user_id, symbol))
    if existing_asset is None:
        session.add(Asset(owner_id=user_id, 
            asset_symbol=symbol, asset_amount=amount))
    else:
        existing_asset.asset_amount += amount
    session.commit()

    return session.query(Asset).get((user_id, symbol))


def benchmark_sqlite(n_rounds: int = 1,
                     sqlite_path: str = DEFAULT_SQLITE_PATH):
    """Remove existing benchmark.chives.sqlite, create a new one, initialize
    database schema, create buyer/seller/company, then for each round, submit 
    an order into the rabbitMQ. After all rounds, wait until transaction 
    n_rounds exists, then report correctness and runtime.

    This method is not responsible (and is unable to) for spawnning matching 
    engines

    :param sqlite_path: [description], defaults to DEFAULT_SQLITE_PATH
    :type sqlite_path: str, optional
    :param n_workers: [description], defaults to 1
    :type n_workers: int, optional
    :param n_rounds: [description], defaults to 1
    :type n_rounds: int, optional
    """
    # Set up database schema
    remove_old_sqlite(sqlite_path)
    sql_engine = create_engine(f"sqlite:///{sqlite_path}")
    Base.metadata.create_all(sql_engine)
    Session = sessionmaker(bind=sql_engine)
    main_session = Session()

    # Set up initial data
    buyer = add_user("buyer", "password", main_session)
    seller = add_user("seller", "password", main_session)
    bench_company = add_company("BENCH", seller.user_id, main_session)
    inject_asset(seller.user_id, "_CASH", 10000000, main_session)
    inject_asset(buyer.user_id, "_CASH", 10000000, main_session)

    # Set up RabbitMQ connection
    mq = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    ch = mq.channel()
    ch.queue_declare(queue='incoming_order')

    # Generate random prices and sizes, then in sequential rounds, submit the 
    # pairs of orders
    random_sizes = [random.randint(1, 100) for i in range(n_rounds)]
    random_prices = [random.uniform(10, 100) for i in range(n_rounds)]
    start_dttm = dt.datetime.utcnow()
    for i in range(n_rounds):
        random_size, random_price = random_sizes[i], random_prices[i]
        injected_asset = inject_asset(
            seller.user_id, bench_company.symbol, random_size, main_session)
        injected_asset.asset_amount -= random_size
        main_session.commit()
        ask = Order(
            security_symbol=bench_company.symbol,
            side="ask",
            size=random_size,
            price=random_price,
            owner_id=seller.user_id
        )
        bid = Order(
            security_symbol=bench_company.symbol,
            side="bid",
            size=random_size,
            price=None,
            owner_id=buyer.user_id
        )
        ch.basic_publish(
            exchange='', routing_key='incoming_order', body=ask.json)
        ch.basic_publish(
            exchange='', routing_key='incoming_order', body=bid.json)
    
    # Wait until there are as many transactions as there are rounds
    while main_session.query(Transaction).count() < n_rounds:
        time.sleep(1)
    # Check the transaction size and price, then report result
    for i in range(n_rounds):
        tr = main_session.query(Transaction).get(i+1)
        if tr.size != random_sizes[i]:
            print(f"{tr} size mismatches expected size {random_sizes[i]}")
        if tr.price != random_prices[i]:
            print(f"{tr} price mismatches expected price {random_prices[i]}")
    print("Benchmark correctness verified")
    finish_dttm = main_session.query(Transaction).get(n_rounds).transact_dttm
    print(f"Benchmark runtime: {finish_dttm - start_dttm}")

    # Teardown
    mq.close()
    remove_old_sqlite(sqlite_path)
    print("Benchmark finished")


def benchmark_mysql(n_rounds: int = 1, sql_uri: str = DEFAULT_MYSQL_URI):
    """Remove existing benchmark.chives.sqlite, create a new one, initialize
    database schema, create buyer/seller/company, then for each round, submit 
    an order into the rabbitMQ. After all rounds, wait until transaction 
    n_rounds exists, then report correctness and runtime.

    This method is not responsible (and is unable to) for spawnning matching 
    engines

    :param sqlite_path: [description], defaults to DEFAULT_SQLITE_PATH
    :type sqlite_path: str, optional
    :param n_workers: [description], defaults to 1
    :type n_workers: int, optional
    :param n_rounds: [description], defaults to 1
    :type n_rounds: int, optional
    """
    # Dropping database as a set up is tricky; I will leave it to docker run 
    # and docker stop as setup/teardown

    # Set up schemas
    sql_engine = create_engine(sql_uri)
    Base.metadata.create_all(sql_engine)
    Session = sessionmaker(bind=sql_engine)
    main_session = Session()

    # Set up initial data
    buyer = add_user("buyer", "password", main_session)
    seller = add_user("seller", "password", main_session)
    bench_company = add_company("BENCH", seller.user_id, main_session)
    inject_asset(seller.user_id, "_CASH", 10000000, main_session)
    inject_asset(buyer.user_id, "_CASH", 10000000, main_session)

    # Set up RabbitMQ connection
    mq = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    ch = mq.channel()
    ch.queue_declare(queue='incoming_order')

    # Generate random prices and sizes, then in sequential rounds, submit the 
    # pairs of orders
    random_sizes = [random.randint(1, 100) for i in range(n_rounds)]
    random_prices = [random.uniform(10, 100) for i in range(n_rounds)]
    start_dttm = dt.datetime.utcnow()
    for i in range(n_rounds):
        random_size, random_price = random_sizes[i], random_prices[i]
        injected_asset = inject_asset(
            seller.user_id, bench_company.symbol, random_size, main_session)
        injected_asset.asset_amount -= random_size
        main_session.commit()
        ask = Order(
            security_symbol=bench_company.symbol,
            side="ask",
            size=random_size,
            price=random_price,
            owner_id=seller.user_id
        )
        bid = Order(
            security_symbol=bench_company.symbol,
            side="bid",
            size=random_size,
            price=None,
            owner_id=buyer.user_id
        )
        ch.basic_publish(
            exchange='', routing_key='incoming_order', body=ask.json)
        ch.basic_publish(
            exchange='', routing_key='incoming_order', body=bid.json)
    print("All orders submitted")
    
    # Use .close() to reset the connection since we are now querying results 
    # that were modified by an SQLAlchemy ORM Session in a different process
    main_session.close(); time.sleep(1)
    print("Main session reset; waiting for 1 seconds before next query")
    # import pdb; pdb.set_trace()
    time.sleep(1)
    while main_session.query(Transaction).count() < n_rounds:
        main_session.close(); time.sleep(1)
    
    # Check the transaction size and price, then report result
    for i in range(n_rounds):
        tr = main_session.query(Transaction).get(i+1)
        if tr.size != random_sizes[i]:
            print(f"{tr} size mismatches expected size {random_sizes[i]}")
        if abs(tr.price - random_prices[i]) > 0.01:
            print(f"{tr} price mismatches expected price {random_prices[i]}")
    print("Benchmark correctness verified")
    finish_dttm = main_session.query(Transaction).get(n_rounds).transact_dttm
    print(f"Benchmark runtime: {finish_dttm - start_dttm}")

    # Teardown
    mq.close()
    print("Benchmark finished")
