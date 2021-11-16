from flask import Flask, render_template, redirect, url_for, request
from db_creator import init_db
from datetime import datetime, timedelta
import time
import requests
import csv
import os
import matplotlib.pyplot as plt
from flask_login import login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt

app = Flask(__name__)
Users, Stock, UsersActions, db = init_db(app)
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = 'tojestsekretnyklucz'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


class Wallet:
    
    TAX = 0.19
    COMM_PERC = 0.0038
    AV_KEY = '***' # Alpha Vantage API

    def __init__(self, username):
        self.username = username
        self.today = datetime.today()
        self.today_str = self.set_date_format(self.today)
        self.today_iso = str(datetime.isoweekday(datetime.today()))
        self.user_symbols = self.set_user_symbols()
        self.stock_date = self.set_stock_date()
        self.user_wallets = self.set_user_wallets()

    def set_date_format(self, date):
        return f'{str(date.day)}-{str(date.month)}-{str(date.year)}' # format daty DD-MM-YYYY

    def date_value(self, date_str):
        return int(date_str[0:2]) + (int(date_str[3:5])**3)*10 + int(date_str[6:]) # format daty DD-MM-YYYY

    def set_stock_date(self):
        stock = Stock.query.all()
        max_date_value = 0
        for item in stock:
            date_value = self.date_value(item.date)
            if date_value >= max_date_value:
                max_date_value = date_value
                stock_date = item.date
        max_date_symbols = [item.symbol for item in stock if item.date == stock_date]
        for symbol in self.user_symbols:
            if symbol not in max_date_symbols:
                user_stock = Stock.query.filter_by(user=self.username).all()
                if user_stock:
                    date_values = {}
                    for item in user_stock:
                        date_values[self.date_value(item.date)] = item.date
                    return date_values[max(date_values)]
            continue
        return stock_date

    def download_AV_stock_symbols(self): # Alpha Vantage API
        CSV_URL = f'https://www.alphavantage.co/query?function=LISTING_STATUS&state=active&apikey={self.AV_KEY}'
        with requests.Session() as s:
            download = s.get(CSV_URL)
            decoded_content = download.content.decode('utf-8')
            cr = csv.reader(decoded_content.splitlines(), delimiter=',')
            my_list = list(cr)
            del my_list[0]
            return [row[0] for row in my_list]

    def set_user_symbols(self):
        user_symbols = set()
        user_actions = UsersActions.query.filter_by(user=self.username).all()
        return list(set(
            [action.symbol for action in user_actions if action.symbol not in user_symbols]))

    def set_user_wallets(self):
        user_wallets_names = set()
        user_wallets = {}
        user_actions = UsersActions.query.filter_by(user=self.username).all()
        user_wallets_names = set(
            [action.name for action in user_actions if action.name not in user_wallets_names])
        for name in user_wallets_names:
            user_wallets[name] = [obj for obj in user_actions if obj.name == name]
        return user_wallets

    def download_AV_price(self, source): # Alpha Vantage API
        r = requests.get(source)
        weekend = {'1': 3, '7': 2}
        if self.today_iso in weekend:
            return r.json()['Time Series (Daily)'][str(self.today.date()-timedelta(weekend[self.today_iso]))]['4. close']
        return r.json()['Time Series (Daily)'][str(self.today.date()-timedelta(1))]['4. close']

    def update_stock(self):
        today_stock = Stock.query.filter_by(date=self.today_str).all()
        today_stock_symbols = set()
        today_stock_symbols = set([obj.symbol for obj in today_stock])
        if today_stock_symbols:
            for symbol in today_stock_symbols:
                if symbol in self.user_symbols:
                    self.user_symbols.remove(symbol)
        if self.user_symbols:
            i = 0
            for symbol in self.user_symbols:
                AV_api_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={self.AV_KEY}' # Alpha Vantage API
                price = self.download_AV_price(AV_api_url) # Alpha Vantage API
                stock = Stock(
                    symbol = symbol,
                    price = price,
                    date = self.today_str,
                    user = self.username
                    )
                db.session.add(stock)
                db.session.commit()
                i += 1
                if i % 5 == 0 and i != len(self.user_symbols):
                    time.sleep(58) # Alpha Vantage API
            return True
        return False

    def get_wallet_values(self, wallet, stock_by_date):
        wallet_income = round(float(), 2)
        wallet_invest = round(float(), 2)
        for action in wallet:
            for obj in stock_by_date:
                if action.symbol == obj.symbol:
                    invest = float(action.price) * float(action.quantity)
                    income = float(obj.price) * float(action.quantity)
                    wallet_invest += invest
                    wallet_income += income
        wallet_profit = wallet_income - wallet_invest
        if wallet_profit > 0:
            wallet_profit *= (1 - self.TAX)
        wallet_profit -= (wallet_income * self.COMM_PERC)
        wallet_profit = round(wallet_profit, 2)
        if not wallet_invest:
            wallet_invest = 1
        try:
            wallet_perc = round((wallet_profit / wallet_invest) * 100, 1)
        except ZeroDivisionError:
            wallet_perc = 0
        return {
            'wallet_invest' : round(wallet_invest, 2),
            'wallet_profit' : wallet_profit,
            'wallet_perc' : wallet_perc
        }

    def get_user_dates(self):
        stock = Stock.query.all()
        return [act.date for act in stock if act.symbol == self.user_symbols[0]]
    
    def wallet_plot(self, name, wallet):
        if os.path.exists(f'{name}.jpg'):
            os.remove(f'{name}.jpg')
        user_dates = self.get_user_dates()
        wallet_profits = [0]
        for date in user_dates:
            stock_by_date = Stock.query.filter_by(date=date).all()
            wallet_profits.append(self.get_wallet_values(wallet, stock_by_date)['wallet_profit'])
        plt.plot(wallet_profits)
        plt.savefig(f'{name}.jpg')
        
    def set_dol_c(self, y, z):
        if not y:
            y = 0
        if not z:
            z = 0
        if int(z) >= 0:
            y = float(y)
            if int(z) < 10:
                z = '0.0' + str(z)
            elif int(z) > 10:  
                O_z = '0.' + str(z)
                z = round(float(O_z), 2)
                z = str(z)[0 : 4]
            z = float(z)
        return str(y + z)


class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Nazwa użytkownika"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Hasło"})
    submit = SubmitField("Zarejestruj")
    def validate_username(self, username):
        existing_user_name = Users.query.filter_by(
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
        user = Users.query.filter_by(username=form.username.data).first()
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
        new_user = Users(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template("register.html", form=form)

@app.route('/logout/', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route("/home/", methods=["GET", "POST"])
@login_required
def home():
    cw = Wallet(current_user.username)
    if request.method == "POST":
        cw.update_stock()
        return redirect(url_for('home'))
    stock_by_date = Stock.query.filter_by(date=cw.stock_date).all()
    user_actions = UsersActions.query.filter_by(user=current_user.username).all()
    wallets_values = {}
    all_wallets_values = cw.get_wallet_values(user_actions, stock_by_date)
    for name in cw.user_wallets:
        wallets_values[f'{name}'] = cw.get_wallet_values(cw.user_wallets[f'{name}'], stock_by_date)
        # cw.wallet_plot(name, cw.user_wallets[f'{name}'])
    context = {
        "stock_date" : cw.stock_date,
        "all_wallets_values" : all_wallets_values,
        "wallets_values" : wallets_values,
        "user" : current_user.username
    }
    return render_template("home.html", context=context)

@app.route("/create_wallet/", methods=["GET", "POST"])
@login_required
def create_wallet():
    cw = Wallet(current_user.username)
    n = request.form.get('name')
    s = request.form.get('symbol')
    ps = request.form.get('price_s')
    pc = request.form.get('price_c')
    q = request.form.get('quantity')
    w = float(cw.set_dol_c(ps, pc))
    if n:
        investment = UsersActions(
            name = n,
            user = current_user.username,
            symbol = s,
            price = w,
            quantity = q
            )
        db.session.add(investment)
        db.session.commit()
    user_actions = UsersActions.query.filter_by(
        user=current_user.username).all()
    wallets_n = [wallet for wallet in user_actions if wallet.name == n]
    today_symbols = cw.download_AV_stock_symbols()
    context = {
        "stock_date" : cw.stock_date,
        "symbols" : today_symbols,
        "user_symbols" : cw.user_symbols,
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
    cw = Wallet(current_user.username)
    context = {
        "stock_date" : cw.stock_date,
        "wallets" : cw.user_wallets,
        "user" : current_user.username
    }
    return render_template("show.html", context=context)

# ***********************************************************************************************

if __name__ == '__main__':
    app.run(debug=True)
