from flask import Flask, render_template, redirect, url_for, request
from wallets import Wallet
from datetime import datetime, timedelta
import time
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt

app = Flask(__name__)
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wallets.db'
app.config['SECRET_KEY'] = 'tojestsekretnyklucz'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(80), nullable=False)


class StockData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(20), unique=False, nullable=False)
    price = db.Column(db.Float, unique=False, nullable=False)
    data = db.Column(db.String(20), unique=False, nullable=False)


class UsersWallets(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String(80), unique=False, nullable=False)
    name = db.Column(db.String(80), unique=False, nullable=False)
    symbol = db.Column(db.String(20), unique=False, nullable=False)
    price = db.Column(db.Float, unique=False, nullable=False)
    quantity = db.Column(db.Integer, unique=False, nullable=False, server_default="", default="")


db.create_all()


class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Nazwa użytkownika"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Hasło"})
    submit = SubmitField("Zarejestruj")
    def validate_username(self, username):
        existing_user_name = User.query.filter_by(
            username=username.data).first()
        if existing_user_name:
            raise ValidationError(
                "Ta nazwa użytkownika już istnieje. Proszę wybrać inną nazwę.")


class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Nazwa użytkownika"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Hasło"})
    submit = SubmitField("Zaloguj")


@app.route("/")
@app.route("/login/", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('home'))
    return render_template("login.html", form=form)

@app.route("/register/", methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template("register.html", form=form)

@app.route('/logout/', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

w0 = Wallet(0,'')
symbols = w0.symbols_list

def date_value(date):
    return int(date[0:4]) + (int(date[5:7])**3)*10 + int(date[8:])

def set_stock_date():
    stock_data = StockData.query.all()
    date_values = {}
    for row in stock_data:
        if row.data == w0.act_date:
            return row.data
    for row in stock_data:
        date_values[date_value(row.data)] = row.data
    return date_values[max(date_values)]

@app.route("/home/", methods=["GET", "POST"])
@login_required
def home():
    api_key = ''
    if request.method == "POST":
        api_key = '***'
    w0 = Wallet(0,api_key)
    wallets = {}
    for i in range(1, w0.wallets_amount):
        wallets[f'w{i}'] = Wallet(i, api_key)
    stock_date = set_stock_date()
    context = {
        "stock_date" : stock_date,
        "wallets_invest" : w0.wallet_invest,
        "wallets_profit" : w0.wallet_profit,
        "wallets_perc" : w0.wallet_perc,
        "wallets" : wallets,
        "user" : current_user.username
    }
    return render_template("home.html", context=context)

@app.route("/create_wallet/", methods=["GET", "POST"])
@login_required
def create_stock_data():
    n = request.form.get('name')
    s = request.form.get('symbol')
    ps = request.form.get('price_s')
    pc = request.form.get('price_c')
    q = request.form.get('quantity')
    w = float(w0.set_dol_c(ps, pc))
    if n:
        if s not in symbols:
            return "<h1>Nie ma takiej spółki</H1>"
        investment = UsersWallets(
            name = n,
            user = current_user.username,
            symbol = s,
            price = w,
            quantity = q
            )
        db.session.add(investment)
        db.session.commit()
    current_user_wallets = UsersWallets.query.filter_by(
        user=current_user.username).all()
    wallets_n = [wallet for wallet in current_user_wallets if wallet.name == n]
    stock_date = set_stock_date()
    context = {
        "stock_date" : stock_date,
        "symbols" : symbols,
        "wallet_n" : wallets_n,
        "number" : n,
        "symbol" : s,
        "price" : w,
        "quantity" : q,
        "user" : current_user.username
    }
    return render_template("wallet.html", context=context)

@app.route("/show_wallets/")
@login_required
def show_wallets():
    symbols = set()
    wallets = {}
    current_wallets_names = set()
    current_user_wallets = UsersWallets.query.filter_by(user=current_user.username).all()
    current_wallets_names = set(
        [wallet.name for wallet in current_user_wallets if wallet.name not in current_wallets_names])
    symbols = list(set(
        [wallet.symbol for wallet in current_user_wallets if wallet.symbol not in symbols]))
    for name in current_wallets_names:
        wallets[name] = [obj for obj in current_user_wallets if obj.name == name]
    stock_date = set_stock_date()
    today_stock = StockData.query.filter_by(data=stock_date).all()
    today_symbols = [obj.symbol for obj in today_stock if today_stock]
    for symbol in today_symbols:
        if symbol in symbols:
            symbols.remove(symbol)
    if symbols:
        i = 0
        for symbol in symbols:
            api_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey=L9D9N4VGYSZN3WNW'
            price = w0.get_api(api_url)
            stock = StockData(
                symbol = symbol,
                price = price,
                data = w0.act_date
                )
            db.session.add(stock)
            db.session.commit()
            i += 1
            if i % 5 == 0:
                time.sleep(58)
    context = {
        "stock_date" : stock_date,
        "wallets" : wallets,
        "user" : current_user.username
    }
    return render_template("show.html", context=context)

if __name__ == '__main__':
    app.run(debug=True)
