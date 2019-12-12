from flask import Flask
from app.config import Config
from flask_login import LoginManager
from flask_mail import Mail
import os
#from flask_bootstrap import Bootstrap

app = Flask(__name__)
login = LoginManager(app)
login.login_view = 'login'
app.config.from_object(Config)

#bootstrap = Bootstrap(app)

mail_settings = {
    "MAIL_SERVER": 'smtp.gmail.com',
    "MAIL_PORT": 465,
    "MAIL_USE_TLS": False,
    "MAIL_USE_SSL": True,
    "MAIL_USERNAME": 'ecetest970@gmail.com',
    "MAIL_PASSWORD": 'ece1779master'
}

app.config.update(mail_settings)
mail = Mail(app)

from app import routes