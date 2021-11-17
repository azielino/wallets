from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

def init_db(app):

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wallets.db'
    db = SQLAlchemy(app)


    class Users(db.Model, UserMixin):
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(20), nullable=False, unique=True)
        password = db.Column(db.String(80), nullable=False)


    class Stock(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        symbol = db.Column(db.String(20), unique=False, nullable=False)
        price = db.Column(db.Float, unique=False, nullable=False)
        date = db.Column(db.String(20), unique=False, nullable=False)
        user = db.Column(db.String(20), unique=False, nullable=False)


    class UsersActions(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        user = db.Column(db.String(80), unique=False, nullable=False)
        name = db.Column(db.String(80), unique=False, nullable=False)
        symbol = db.Column(db.String(20), unique=False, nullable=False)
        price = db.Column(db.Float, unique=False, nullable=False)
        quantity = db.Column(db.Integer, unique=False, nullable=False)
        start_date = db.Column(db.String(12), unique=False, nullable=False)

    
    db.create_all()
    return Users, Stock, UsersActions, db