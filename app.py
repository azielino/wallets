from flask import Flask, render_template, redirect, url_for, request
from db_creator import init_db
from datetime import datetime, timedelta
import time
import requests
import csv
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
    AV_KEY = 'L9D9N4VGYSZN3WNW' # Alpha Vantage API

    def __init__(self, username):
        self.username = username
        self.today = datetime.today()
        self.today_str = self.set_today_str()
        self.today_iso = str(datetime.isoweekday(datetime.today()))
        self.stock_date = self.set_stock_date()
        self.user_symbols = self.set_user_symbols()
        self.user_wallets = self.set_user_wallets()

    def set_today_str(self):
        today = datetime.today()
        return f'{str(today.day)}-{str(today.month)}-{str(today.year)}' # format daty DD-MM-YYYY

    def date_value(self, date_str):
        return int(date_str[0:2]) + (int(date_str[3:5])**3)*10 + int(date_str[6:]) # format daty DD-MM-YYYY

    def set_stock_date(self):
        stock_data = Stock.query.all()
        if stock_data:
            date_values = {}
            for row in stock_data:
                if row.date == self.today_str:
                    return row.date
            for row in stock_data:
                date_values[self.date_value(row.date)] = row.date
            return date_values[max(date_values)]

    def download_AV_stock_symbols(self): # Alpha Vantage API
        CSV_URL = f'https://www.alphavantage.co/query?function=LISTING_STATUS&state=active&apikey={self.AV_KEY}'
        with requests.Session() as s:
            download = s.get(CSV_URL)
            decoded_content = download.content.decode('utf-8')
            cr = csv.reader(decoded_content.splitlines(), delimiter=',')
            my_list = list(cr)
            return [row[0] for row in my_list]

    def set_user_symbols(self):
        user_symbols = set()
        user_actions = UsersActions.query.filter_by(user=self.username).all()
        user_symbols = list(set(
            [action.symbol for action in user_actions if action.symbol not in user_symbols]))
        return user_symbols

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
        if self.stock_date == self.today_str:
            stock = Stock.query.filter_by(date=self.stock_date).all()
            stock_symbols = set()
            stock_symbols = set([obj.symbol for obj in stock])
            for symbol in stock_symbols:
                if symbol in self.user_symbols:
                    self.user_symbols.remove(symbol)
        stock = None
        if self.user_symbols:
            i = 0
            for symbol in self.user_symbols:
                AV_api_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={self.AV_KEY}' # Alpha Vantage API
                price = self.download_AV_price(AV_api_url) # Alpha Vantage API
                stock = Stock(
                    symbol = symbol,
                    price = price,
                    date = self.today_str
                    )
                db.session.add(stock)
                db.session.commit()
                i += 1
                if i % 5 == 0:
                    time.sleep(58) # Alpha Vantage API
        return stock

    def get_wallet_values(self, wallet, stock):
        wallet_income = round(float(), 2)
        wallet_invest = round(float(), 2)
        for action in wallet:
            for obj in stock:
                if action.symbol == obj.symbol:
                    invest = float(action.price) * float(action.quantity)
                    income = float(obj.price) * float(action.quantity)
                    wallet_invest += invest
                    wallet_income += income
        wallet_profit = wallet_income - wallet_invest
        wallet_profit *= (1 - self.TAX)
        wallet_profit -= (wallet_income * self.COMM_PERC)
        wallet_profit = round(wallet_profit, 2)
        if not wallet_invest:
            wallet_invest = 1
        wallet_perc = round((wallet_profit / wallet_invest) * 100, 1)
        return {
            'wallet_invest' : round(wallet_invest, 2),
            'wallet_profit' : wallet_profit,
            'wallet_perc' : wallet_perc
        }

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
    stock = Stock.query.filter_by(date=cw.stock_date).all()
    user_actions = UsersActions.query.filter_by(user=current_user.username).all()
    wallets_values = {}
    all_wallets_values = cw.get_wallet_values(user_actions, stock)
    for name in cw.user_wallets:
        wallets_values[f'{name}'] = cw.get_wallet_values(cw.user_wallets[f'{name}'], stock)
    context = {
        "stock_date" : cw.stock_date,
        "all_wallets_values" : all_wallets_values,
        "wallets_values" : wallets_values,
        "user" : current_user.username
    }
    return render_template("home.html", context=context)

@app.route("/create_wallet/", methods=["GET", "POST"])
@login_required
def create_stock_data():
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
    context = {
        "stock_date" : cw.stock_date,
        "symbols" : cw.download_AV_stock_symbols(),
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
