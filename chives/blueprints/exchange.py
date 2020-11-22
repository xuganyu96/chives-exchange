from flask import (
    Blueprint, flash, g as flask_g, redirect, render_template, request, 
    session as flask_session, url_for
)
from flask_login import login_required, current_user
import pika
from pika.exceptions import AMQPConnectionError

from chives.db import get_db, get_mq
from chives.forms import OrderSubmitForm
from chives.models.models import Order, Asset

bp = Blueprint("exchange", __name__, url_prefix="/exchange")

@bp.route("/dashboard", methods=("GET",))
@login_required
def dashboard():
    # Any amount of cash will be displayed
    cash = [a for a in current_user.assets if (a.asset_symbol == "_CASH")][0]
    # Empty assets for stocks will not be displayed
    stocks = [a for a in current_user.assets 
        if (a.asset_symbol != "_CASH") and (a.asset_amount > 0)]
    return render_template(
        "exchange/dashboard.html", cash=cash, stocks=stocks)

@bp.route("/submit_order", methods=("GET", "POST"))
@login_required
def submit_order():
    # Even before rendering the page, try to connect to RabbitMQ. If RabbitMQ 
    # is not running, then redirect to an error page
    mq = ch = None
    try:
        mq: pika.BlockingConnection = get_mq()
        ch = mq.channel()
        ch.queue_declare(queue='incoming_order')
    except AMQPConnectionError as e:
        error_msg = "Webserver failed to connect to order queue"
        return redirect(url_for("exchange.error", error_msg=error_msg))

    form = OrderSubmitForm(request.form)
    if request.method == "POST" and form.validate_on_submit():
        new_order: Order = Order(
            security_symbol=form.security_symbol.data, 
            side=form.side.data, 
            size=form.size.data, 
            price=form.price.data,
            all_or_none=form.all_or_none.data,
            immediate_or_cancel=form.immediate_or_cancel.data,
            owner_id=current_user.user_id
        )
        if new_order.side == "ask":
            user_existing_asset = get_db().query(Asset).get(
                (current_user.user_id, new_order.security_symbol))
            if user_existing_asset is None or user_existing_asset.asset_amount < new_order.size:
                return redirect(url_for("exchange.error", error_msg="Insufficient assets"))
            else:
                user_existing_asset.asset_amount -= new_order.size
        if new_order.price is None:
            print("Market order")
            new_order.immediate_or_cancel = True
        db = get_db()
        db.add(new_order)
        db.commit()
        ch.basic_publish(
                exchange='', routing_key='incoming_order', body=new_order.json)

        return redirect(url_for("exchange.dashboard"))
    return render_template("exchange/submit_order.html", form=form)


@bp.route("/error", methods=("GET",))
def error():
    error_msg = "Something went wrong..."
    if 'error_msg' in request.args:
        error_msg = request.args['error_msg']
    return render_template("exchange/error.html", error_msg=error_msg)
