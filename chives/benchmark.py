import datetime as dt
from collections import namedtuple
import logging
import os 
import random
import time

import pika
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy.orm import sessionmaker, Session
from werkzeug.security import generate_password_hash

from chives.models import Base, User, Company, Asset, Order, Transaction


DEFAULT_SQLITE_URI = "sqlite:////tmp/benchmark.chives.sqlite"
DEFAULT_MYSQL_URI = "mysql+pymysql://chives_u:chives_password@localhost:3307/chives"
BenchmarkResult = namedtuple("BenchmarkResult", ["run_seconds", "errors"])

logger = logging.getLogger("chives.benchmark")
logger.setLevel(logging.INFO)
chandle = logging.StreamHandler()
chandle.setLevel(logging.INFO)
formatter = logging.Formatter(
    '[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s')
chandle.setFormatter(formatter)
logger.addHandler(chandle)


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


def _benchmark(sql_session: Session, 
        queue_conn: pika.BlockingConnection, n_rounds: int) -> dt.datetime:
    """The core logic of the benchmark: add pseudo users and bench company, 
    inject assets, generate random sizes and prices, create stock order objects, 
    then submit them to the queue

    :param sql_session: [description]
    :type sql_session: Session
    :param queue_conn: [description]
    :type queue_conn: pika.BlockingConnection
    :param n_rounds: [description]
    :type n_rounds: int
    :return: A start datetime
    :rtype: dt.datetime
    """
    # Open Message Queue channel
    ch = queue_conn.channel()
    ch.queue_declare(queue='incoming_order')

    # Set up initial data
    buyer = add_user("buyer", "password", sql_session)
    seller = add_user("seller", "password", sql_session)
    bench_company = add_company("BENCH", seller.user_id, sql_session)
    inject_asset(seller.user_id, "_CASH", 10000000, sql_session)
    inject_asset(buyer.user_id, "_CASH", 10000000, sql_session)
    random_sizes = [random.randint(1, 100) for i in range(n_rounds)]
    random_prices = [random.uniform(10, 100) for i in range(n_rounds)]

    start_dttm = dt.datetime.utcnow()
    for i in range(n_rounds):
        random_size, random_price = random_sizes[i], random_prices[i]
        injected_asset = inject_asset(
            seller.user_id, bench_company.symbol, random_size, sql_session)
        injected_asset.asset_amount -= random_size
        sql_session.commit()
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
            owner_id=buyer.user_id,
            immediate_or_cancel=True
        )
        ch.basic_publish(
            exchange='', routing_key='incoming_order', body=ask.json)
        ch.basic_publish(
            exchange='', routing_key='incoming_order', body=bid.json)
    
    return start_dttm


def benchmark(n_rounds: int = 1, sql_uri: str = DEFAULT_SQLITE_URI, 
              verify_integrity: bool = True):
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
    :param verify_integrity: if set to True, stops the benchmark after all orders are 
    submitted, then return a BenchmarkResult with 0 second runtime and error 
    message "dry run"
    """
    # Set up database schema
    logger.info(f"""Starting benchmark session: 
    number of rounds: {n_rounds}
    Database URI: {sql_uri}""")
    main_engine = create_engine(sql_uri)
    Base.metadata.drop_all(main_engine) # it's okay to repeatedly run drop_all
    Base.metadata.create_all(main_engine)
    Session = sessionmaker(bind=main_engine)
    main_session = Session()
    logger.info(f"""Database schemas dropped and re-created""")

    # Set up RabbitMQ connection
    mq = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    logger.info(f"RabbitMQ connected")

    # Start the initiation part of the benchmark
    start_dttm = _benchmark(main_session, mq, n_rounds)
    logger.info("All order messages submitted to queue")
    
    if not verify_integrity:
        # Finish the benchmark without computing runtime or correctness
        logger.info("Skipped integrity verification. Benchmark finished")
        return BenchmarkResult(0, ["Skipped verifying integrity"])
    else:
        # Wait until all messages have been processed
        msg_count = mq.channel().queue_declare(
            queue='incoming_order', passive=True).method.message_count
        logger.info(msg_count)
        while msg_count > 0:
            logger.info(msg_count)
            msg_count = mq.channel().queue_declare(
                queue='incoming_order', passive=True).method.message_count
        
        logger.info("Integrity verified. Benchmark finished")

        # Don't forget to close the active connections
        mq.close()
        return BenchmarkResult(0, [])
