from flask_wtf import FlaskForm as Form
from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, validators)

class RegistrationForm(Form):
    username = StringField(
        label='username', validators=[validators.InputRequired(), validators.Length(min=4, max=25)])
    password = PasswordField(label='password', validators=[
        validators.InputRequired(),
        validators.EqualTo('confirm', message="Passwords must match")]
    )
    confirm = PasswordField("confirm password")
    submit = SubmitField("Sign up")
