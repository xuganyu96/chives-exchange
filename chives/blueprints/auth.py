import functools 

from flask import (
    Blueprint, flash, g as flask_g, redirect, render_template, request, 
    session as flask_session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash 

from chives.db import get_session as get_db_session
from chives.forms import RegistrationForm, LoginForm
from chives.models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

@bp.route("/register", methods=("GET", "POST"))
def register():
    form = RegistrationForm(request.form)
    if request.method == "POST" and form.validate_on_submit():
        db_session = get_db_session()
        if db_session.query(User).filter(
            User.username==form.username.data).first() is not None:
            form.username.errors.append("Username already taken!")
        else:
            new_user: User = User(
                username=form.username.data, 
                password_hash=generate_password_hash(form.password.data))
            db_session.add(new_user)
            db_session.commit()
            print("User created")

            return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=("GET", "POST"))
def login():
    form = LoginForm(request.form)
    if request.method == "POST" and form.validate_on_submit():
        db_session = get_db_session()
        user = db_session.query(
            User).filter(User.username==form.username.data).first()
        if (user is not None) and check_password_hash(user.password_hash, 
                                                      form.password.data):
            flask_session.clear()
            flask_session['user_id'] = user.user_id 
            return redirect(url_for('debug.can_connect'))
        else:
            form.password.errors.append(
                "Login failed; check your username and password")
    
    return render_template("auth/login.html", form=form)

@bp.route("/logout")
def logout():
    flask_session.clear()
    return redirect(url_for("auth.login"))


@bp.before_app_request 
def load_logged_in_user():
    user_id = flask_session.get('user_id')

    if user_id is None:
        flask_g.user = None 
    else:
        db_session = get_db_session()
        flask_g.user = db_session.query(User).get(user_id)


def login_required(view):
    @functools.wraps(view)
    def authenticated_view(**kwargs):
        if flask_g.user is None:
            return redirect(url_for("auth.login"))
        return view(**kwargs)
    
    return authenticated_view