"""
All test cases written in this file test the orders only. The matching engine 
supplied in this module does not ignore user logic
"""
from collections.abc import Iterable
import typing as ty

import pytest
from sqlalchemy.engine import Engine as SQLEngine

from chives.matchingengine.matchingengine import MatchingEngine
from chives.models.models import Order, Transaction, User, Asset


@pytest.fixture
def matching_engine(sql_engine: SQLEngine) -> MatchingEngine:
    """Return a matching engine using the sql_engine obtained from top-level 
    fixture, and with user logic ignored

    :param sql_engine: [description]
    :type sql_engine: [type]
    :return: [description]
    :rtype: MatchingEngine
    """
    me = MatchingEngine(sql_engine)
    return me

@pytest.fixture 
def user_inject(matching_engine) -> ty.Callable:
    """Given a matching engine, return a method that takes a username , insert a dummy user(s) into the database, and return 
    the user object(s) in the same order

    :param matching_engine: [description]
    :type matching_engine: [type]
    :return: [description]
    :rtype: ty.Callable
    """
    def _user_inject(username: str):
        new_user = User(username=username, password_hash="password")
        matching_engine.session.add(new_user)
        matching_engine.session.commit()
        return new_user
    
    return _user_inject


def test_unmatched_market_order(matching_engine, user_inject):
    """Create a user

    :param matching_engine: [description]
    :type matching_engine: [type]
    """
    user1 = user_inject("user1")
    assert matching_engine.session.query(User).get(1) is user1
