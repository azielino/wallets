from tasks import Users, Stock, UsersActions
from datetime import datetime, timedelta
import os
from flask_creator import flask_app
from flask_login import LoginManager
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt(flask_app)
flask_app.config['SECRET_KEY'] = 'tojestsekretnyklucz'

login_manager = LoginManager()
login_manager.init_app(flask_app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


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


class Wallet:  
    
    TAX = 0.19
    COMM_PERC = 0.0038

    def __init__(self, username):
        self.username = username
        self.user_actions = UsersActions.query.filter_by(user=self.username).all()
        self.today = datetime.today().date()
        self.user_symbols = self.set_user_symbols()
        self.stock_date = self.set_stock_date()
        self.symbols_to_update = self.set_symbols_to_update()
        self.user_wallets = self.set_user_wallets()

    def set_stock_date(self):
        if Stock.query.all():
            return Stock.query.all()[-1].date

    def del_prev_plot_all(self, start_date, date, username):
        date_str = str(date)
        while date_str != start_date:
            date -= timedelta(days=1)
            date_str = str(date)
            if os.path.exists(f'static/{date_str}_{username}_all.jpg'):
                os.remove(f'static/{date_str}_{username}_all.jpg')

    def del_prev_plot_user(self, start_date, date, username, name):
        date_str = str(date)
        while date_str != start_date:
            date -= timedelta(days=1)
            date_str = str(date)
            if os.path.exists(f'static/{date_str}_{username}_{name}.jpg'):
                os.remove(f'static/{date_str}_{username}_{name}.jpg')

    def set_user_symbols(self):
        user_symbols = set()
        if self.user_actions:
            return list({action.symbol for action in self.user_actions if action.symbol not in user_symbols})
        return user_symbols

    def set_user_wallets(self):
        user_wallets_names = set()
        user_wallets = {}
        if self.user_actions:
            user_wallets_names = {
                action.name for action in self.user_actions if action.name not in user_wallets_names}
            for name in user_wallets_names:
                user_wallets[name] = [act for act in self.user_actions if act.name == name]
        return user_wallets
    
    def set_symbols_to_update(self):
        act_stock = Stock.query.filter_by(date=str(self.today - timedelta(days=1))).all()
        act_stock_symbols = {obj.symbol for obj in act_stock}
        if act_stock_symbols:
            return [symbol for symbol in self.user_symbols if symbol not in act_stock_symbols]
        else: 
            return self.user_symbols

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

    def wallet_plot_data(self, wallet, start_date):
        stock = Stock.query.all()
        user_dates = list({item.date for item in stock if item.symbol in self.user_symbols})
        user_dates = sorted(user_dates)
        for date in user_dates:
            if date != start_date:
                del date
            else:
                break
        wallet_dates = user_dates
        wallet_profits = []
        x_axis = []
        for date in wallet_dates:
            stock_by_date = Stock.query.filter_by(date=date).all()
            y = self.get_wallet_values(wallet, stock_by_date)['wallet_profit']
            wallet_profits.append(y)
            x_axis.append(date)
        y_axis = wallet_profits
        return [x_axis, y_axis]

    def set_dol_c(self, y, z):
        if not y:
            y = 0
        if not z:
            z = 0
        if int(z) >= 0:
            y = float(y)
            if int(z) < 10:
                z = '0.0' + str(int(z))
            elif int(z) > 10:  
                O_z = '0.' + str(z)
                z = round(float(O_z), 2)
                z = str(z)[0 : 4]
            z = float(z)
        return str(y + z)