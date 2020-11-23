from flask import (
    Blueprint, flash, g as flask_g, redirect, render_template, request, 
    session as flask_session, url_for
)
from flask_login import login_required, current_user
import pika
from pika.exceptions import AMQPConnectionError

from chives.db import get_db, get_mq
from chives.forms import OrderSubmitForm, StartCompanyForm
from chives.models.models import Order, Asset, Company, Transaction

bp = Blueprint("exchange", __name__, url_prefix="/exchange")

@bp.route("/dashboard", methods=("GET",))
@login_required
def dashboard():
    db = get_db()
    # Any amount of cash will be displayed
    cash = [a for a in current_user.assets if (a.asset_symbol == "_CASH")][0]
    # Empty assets for stocks will not be displayed
    stocks = [a for a in current_user.assets 
        if (a.asset_symbol != "_CASH") and (a.asset_amount > 0)]

    # Compute stocks' market value by company's market price * asset_amount
    # Then compute net worth by summing up cash and stocks market value
    net_worth = cash.asset_amount 
    for stock in stocks:
        market_price = db.query(Company).get(stock.asset_symbol).market_price
        stock.market_value = market_price * stock.asset_amount
        net_worth += stock.market_value
    return render_template("exchange/dashboard.html", 
        cash=cash, stocks=stocks, net_worth=net_worth)

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


@bp.route("/recent_orders", methods=("GET",))
@login_required 
def recent_orders():
    """Render the most recent (up to) 50 orders
    """
    db = get_db()
    ownership = (Order.owner_id == current_user.user_id)
    create_dttm_desc = Order.create_dttm.desc()
    recent_orders = db.query(Order).filter(
        ownership).order_by(create_dttm_desc).limit(50).all()
    for order in recent_orders:
        order.side_display = "Buy" if order.side == "bid" else "Sell"
        order.price_display = f"{order.price:.2f}" if order.price is not None else "any price available"
        order.create_dttm_display = order.create_dttm.strftime("%Y-%m-%d %H:%M:%S")
    
    return render_template("exchange/recent_orders.html", orders=recent_orders)


@bp.route("/recent_transactions", methods=("GET",))
@login_required
def recent_transactions():
    """Render the most recent (up to) 50 transactions
    """
    db = get_db()
    order_ids = [o.order_id for o in current_user.orders]
    involves_current_user = Transaction.ask_id.in_(order_ids) \
        | Transaction.bid_id.in_(order_ids)
    dttm_desc = Transaction.transact_dttm.desc()
    transactions = db.query(Transaction).filter(
        involves_current_user).order_by(dttm_desc).limit(50).all()

    for t in transactions:
        t.side_display = "Bought" if (t.bid_id in order_ids) else "Sold"
        t.dttm_display = t.transact_dttm.strftime("%Y-%m-%d %H:%M:%S")
    
    return render_template("exchange/recent_transactions.html", 
        transactions=transactions)


@bp.route("/start_company", methods=("GET", "POST"))
@login_required 
def start_company():
    form = StartCompanyForm(request.form)
    db = get_db()
    if request.method == "POST" and form.validate_on_submit():
        new_company: Company = Company(
            symbol=form.company_symbol.data,
            name=form.company_name.data,
            initial_value=form.input_cash.data,
            founder_id=current_user.user_id,
            market_price=form.input_cash.data / form.size.data
        )
        db.add(new_company)

        founder_cash = db.query(Asset).get((current_user.user_id, "_CASH"))
        founder_cash.asset_amount -= float(form.input_cash.data)

        # Since this is a new company, the founder will definitely not have 
        # prior assets
        founder_stocks = Asset(
            owner_id=current_user.user_id,
            asset_symbol=form.company_symbol.data,
            asset_amount=form.size.data)
        db.add(founder_stocks)
        db.commit()

        return redirect(url_for("exchange.dashboard"))
    return render_template("exchange/start_company.html", form=form)


@bp.route("/error", methods=("GET",))
def error():
    error_msg = "Something went wrong..."
    if 'error_msg' in request.args:
        error_msg = request.args['error_msg']
    return render_template("exchange/error.html", error_msg=error_msg)
