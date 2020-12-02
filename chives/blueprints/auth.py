import functools 
import logging

from flask import (
    Blueprint, flash, g as flask_g, redirect, render_template, request, 
    session as flask_session, url_for
)
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash 

from chives.webserver import login_manager
from chives.db import get_db
from chives.forms import RegistrationForm, LoginForm
from chives.models import User, Asset


# I am not adding file handler because at deployment, I will use an orchestrator 
# to log console output to a file
logger = logging.getLogger("chives.webserver")
logger.setLevel(logging.DEBUG)
chandle = logging.StreamHandler()
chandle.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s')
chandle.setFormatter(formatter)
logger.addHandler(chandle)

bp = Blueprint("auth", __name__, url_prefix="/auth")

@login_manager.user_loader 
def load_user(user_id):
    db_session = get_db()
    if user_id is not None:
        loaded_user = db_session.query(User).get(user_id)
        logger.info(f"Loading {loaded_user}")
        return loaded_user
    return None


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for("auth.login"))


@bp.route("/register", methods=("GET", "POST"))
def register():
    form = RegistrationForm(request.form)
    if request.method == "POST" and form.validate_on_submit():
        db_session = get_db()
        if db_session.query(User).filter(
            User.username==form.username.data).first() is not None:
            form.username.errors.append("Username already taken!")
        else:
            new_user: User = User(
                username=form.username.data, 
                password_hash=generate_password_hash(form.password.data))
            db_session.add(new_user)
            db_session.commit()
            # Each user receives $10,000.00 of cash upon registration
            initial_cash_amount = 10000
            initial_cash = Asset(
                owner_id=new_user.user_id,
                asset_symbol="_CASH",
                asset_amount=initial_cash_amount
            )
            db_session.add(initial_cash)
            db_session.commit()
            logger.info(f"{new_user} received ${initial_cash_amount:.2f}")

            return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=("GET", "POST"))
def login():
    form = LoginForm(request.form)
    if request.method == "POST" and form.validate_on_submit():
        db_session = get_db()
        user = db_session.query(
            User).filter(User.username==form.username.data).first()
        if (user is not None) and check_password_hash(user.password_hash, 
                                                      form.password.data):
            login_user(user)
            return redirect(url_for('exchange.dashboard'))
        else:
            form.password.errors.append(
                "Login failed; check your username and password")
    
    return render_template("auth/login.html", form=form)

@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
