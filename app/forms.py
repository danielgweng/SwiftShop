from flask import flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField
from wtforms.validators import DataRequired, EqualTo, Required

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')
    

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Confirm', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class UploadForm(FlaskForm):
    file = FileField(validators=[Required()])
    submit = SubmitField('Upload')

class BrowseForm(FlaskForm):
    barcode = StringField('Search by barcode:')
    keyword = StringField('Search by keyword:')
    submit = SubmitField('Search')
    # addToCart = SubmitField('Add Selected Items To Cart')
    def validate(self):
        if (len(self.barcode.data.strip()) > 0) != (len(self.keyword.data.strip()) > 0):
            flash('Search successful.')
            return True
        else:
            flash('You may only use one search option at a time.')
            return False

class CartForm(FlaskForm):
     submit = SubmitField('Go To Payment')
