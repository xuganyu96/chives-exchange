import functools 

from flask import (
    Blueprint, flash, g as flask_g, redirect, render_template, request, 
    session as flask_session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash 

from chives.db import get_session as get_db_session
from chives.forms import RegistrationForm
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
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db_session = get_db_session()
        error = None
        user: User = db_session.query(User).filter(
            User.username == username).first()
        
        if user is None:
            error = "Incorrect username"
        elif not check_password_hash(user.password_hash, password):
            error = "Incorrect password"
        
        if error is None:
            flask_session.clear()
            flask_session['user_id'] = user.user_id 
            return redirect(url_for("index"))
        
        flash(error)
    
    return render_template("auth/login.html")

@bp.route("/logout")
def logout():
    flask_session.clear()
    return redirect(url_for("index"))


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