import datetime as dt
from collections import namedtuple
import logging
import os 
import random
import time
import typing as ty

import pika
from sqlalchemy import create_engine, func
from sqlalchemy.engine import Engine as SQLEngine
from sqlalchemy.orm import sessionmaker, Session
from werkzeug.security import generate_password_hash

from chives.models import (
    Base, User, Company, Asset, Order, Transaction, MatchingEngineLog)
from chives.matchingengine import MatchingEngine


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


def order_tracing(session: Session) -> ty.List[str]:
    """Perform order/transaction integrity verification and return a list of 
    error messages each describing an inconsistency

    :param session: [description]
    :type session: Session
    :return: [description]
    :rtype: ty.List[str]
    """
    errors = []
    session.expire_all()
    n_orders = session.query(Order).count()
    logger.info(f"Inspecting {n_orders} orders")
    for i in range(n_orders):
        inspected_order: Order = session.query(Order).get(i+1)
        if inspected_order.side == "bid":
            trns_filter = Transaction.bid_id == inspected_order.order_id
        else:
            trns_filter = Transaction.ask_id == inspected_order.order_id
        trades = session.query(Transaction).filter(trns_filter).all()
        trade_volume = sum([t.size for t in trades])
        
        if trade_volume == inspected_order.size:
            logger.debug(f"{inspected_order} is fully traded")
        elif trade_volume > inspected_order.size:
            error_msg = f"{inspected_order} is over-traded with volume {trade_volume}"
            logger.warning(error_msg)
            errors.append(error_msg)
        elif trade_volume > 0:
            # inspected_order is partially traded so we look for sub-order 
            suborder = session.query(Order).filter(
                Order.parent_order_id == inspected_order.order_id).first()
            if suborder is None:
                error_msg = f"{inspected_order} is partially fulfilled but no suborder is found"
                logger.warning(error_msg)
                errors.append(error_msg)
            else:
                if suborder.size + trade_volume != inspected_order.size:
                    error_msg = f"{inspected_order}, its remains {suborder}, and trade volume {trade_volume} are inconsistent"
                    logger.warning(error_msg)
                    errors.append(error_msg)
                elif inspected_order.immediate_or_cancel \
                    and suborder.cancelled_dttm is None:
                    error_msg = f"{inspected_order} is IOC, but its remains {suborder} is not cancelled"
                    logger.warning(error_msg)
                    errors.append(error_msg)
            logger.debug(f"{inspected_order} is partially fulfilled and its remaining is correct")
        else:
            # inspected_order is not traded at all 
            if (not inspected_order.active) \
                and (inspected_order.cancelled_dttm is None):
                error_msg = f"{inspected_order} is not traded at all, but it is neither active nor cancelled"
                logger.warning(error_msg)
                errors.append(error_msg)
            else:
                logger.debug(f"{inspected_order} is not traded at all")
    
    return errors


def _benchmark(sql_session: Session, 
        queue_conn: pika.BlockingConnection, n_rounds: int) -> ty.Tuple[
            dt.datetime, ty.List[int], ty.List[float]]:
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
    order_messages = []
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
        sql_session.add(ask)
        sql_session.add(bid)
        sql_session.commit()
        order_messages.append(ask.json)
        order_messages.append(bid.json)
    
    for msg in order_messages:
        ch.basic_publish(
            exchange='', routing_key='incoming_order', body=msg)
    
    return start_dttm, random_sizes, random_prices


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
    start_dttm, random_sizes, random_prices = _benchmark(
        main_session, mq, n_rounds)
    logger.info("All order messages submitted to queue")
    # Once all messages have been submitted, the connection to the rabbitMQ 
    # should be closed immediately; according to the documentation:
    # https://pika.readthedocs.io/en/stable/examples/heartbeat_and_blocked_timeouts.html
    # blocking connection times out after 60 seconds, which means that trying 
    # to close a connection after the timeout will result in an error:
    mq.close()
    logger.info("RabbitMQ connection gracefully closed")
    
    if not verify_integrity:
        # Finish the benchmark without computing runtime or correctness
        logger.info("Skipped integrity verification. Benchmark finished")
        return BenchmarkResult(0, ["Skipped verifying integrity"])
    else:
        # Wait until there are 2 * n_rounds "heartbeat_finished" messages
        hbfinished = MatchingEngineLog.log_msg == MatchingEngine.heartbeat_finish_msg
        while main_session.query(MatchingEngineLog)\
            .filter(hbfinished).count() < (2 * n_rounds):
            main_session.close(); time.sleep(1)
        # Get the last of all heartbeat_finish message
        log_dttm_desc = MatchingEngineLog.log_dttm.desc()
        latest_log = main_session.query(MatchingEngineLog)\
            .filter(hbfinished).order_by(log_dttm_desc).first()
        run_seconds = (latest_log.log_dttm - start_dttm).total_seconds()
        
        error_msgs = order_tracing(main_session)
        logger.info(f"Benchmark finished; {len(error_msgs)} inconsistencies found")

        return BenchmarkResult(run_seconds, error_msgs)
