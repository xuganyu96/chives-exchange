from flask_wtf import FlaskForm as Form
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, IntegerField, 
    SelectField, DecimalField, validators)
from wtforms.validators import InputRequired, Length, EqualTo, NumberRange, Optional

class RegistrationForm(Form):
    username = StringField(
        label='username', validators=[InputRequired(), Length(min=4, max=25)])
    password = PasswordField(label='password', validators=[
        InputRequired(),
        EqualTo('confirm', message="Passwords must match")]
    )
    confirm = PasswordField("confirm password")
    submit = SubmitField("Sign up")

class LoginForm(Form):
    username = StringField(label="username", validators=[InputRequired()])
    password = PasswordField(label="password", validators=[InputRequired()])
    
    submit = SubmitField("Log in")

class OrderSubmitForm(Form):
    side = SelectField(label="side", choices=[('ask', 'selling'), ('bid', 'buying')], validators=[InputRequired()])
    size = IntegerField(label="size", validators=[InputRequired(), NumberRange(min=1, message="Order size must be positive")])
    security_symbol = StringField(label="security_symbol", validators=[InputRequired()])
    price = DecimalField(label="price", places=2, validators=[NumberRange(min=0.01, message="Specified target price must be positive"), Optional()])
    all_or_none = BooleanField(label="all_or_none")
    immediate_or_cancel = BooleanField(label="immediate_or_cancel")

    submit = SubmitField("Place order")
