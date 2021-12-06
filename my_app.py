from flask_creator import flask_app
from flask import render_template, redirect, url_for, request
from tasks import download_AV_stock_symbols, get_AV_stock, save_plot_all, save_plot_wallets, celery
from tasks import Users, Stock, UsersActions, db
from definitons import Wallet, LoginForm, RegisterForm, bcrypt
from datetime import datetime, timedelta
from flask_login import login_user, login_required, logout_user, current_user
import os

today_symbols = download_AV_stock_symbols.delay().get()

@flask_app.route("/")
@flask_app.route("/login/", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('home'))
    return render_template("login.html", form=form)

@flask_app.route("/register/", methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data)
        new_user = Users(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template("register.html", form=form)

@flask_app.route('/logout/', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@flask_app.route("/home/", methods=["GET", "POST"])
@login_required
def home():
    cw = Wallet(current_user.username)
    # isoweekdays = [1, 2, 3, 4, 5, 6]
    # if datetime.isoweekday(datetime.today()) in isoweekdays:
    celery.conf.beat_schedule = {
        'test-every-10-seconds': {
            'task': 'tasks.get_AV_stock',
            'schedule': timedelta(seconds=10),
            'args': (cw.symbols_to_update, current_user.username)
        },
    }
    get_AV_stock.delay(cw.symbols_to_update, current_user.username)
    all_values = {}
    wallets_values = {}
    wallets_plot_data = []
    stock_by_date = Stock.query.filter_by(date=cw.stock_date).all()
    if stock_by_date and cw.user_actions:
        if not os.path.exists(f'static/{cw.stock_date}_{cw.username}_all.jpg'):
            all_values = cw.get_wallet_values(cw.user_actions, stock_by_date)
            all_start_date = cw.user_actions[0].start_date
            cw.del_prev_plot_all(all_start_date, cw.today, current_user.username)
            all_plot_data = cw.wallet_plot_data(cw.user_actions, all_start_date)
            for i in range(1, len(all_plot_data[0])-1):
                all_plot_data[0][i] = i
            save_plot_all.delay(all_plot_data, all_values, cw.stock_date, cw.username)
        for name in cw.user_wallets:
            if not os.path.exists(f'static/{cw.stock_date}_{cw.username}_{name}.jpg'):
                wallets_values[f'{name}'] = cw.get_wallet_values(cw.user_wallets[f'{name}'], stock_by_date)
                wallet_start_date = UsersActions.query.filter_by(name=name).first().start_date
                cw.del_prev_plot_user(wallet_start_date, cw.today, current_user.username, name)
                wallet_plot_data = cw.wallet_plot_data(cw.user_wallets[f'{name}'], wallet_start_date)
                wallets_plot_data.append(wallet_plot_data)
                if wallets_plot_data:
                    save_plot_wallets.delay(wallets_plot_data, wallets_values, name, cw.stock_date, cw.username)
    context = {
        "stock_date" : cw.stock_date,
        "user_wallets" : cw.user_wallets,
        "user" : current_user.username,
    }
    return render_template("home.html", context=context)

@flask_app.route("/create_wallet/", methods=["GET", "POST"])
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
            quantity = q,
            start_date = cw.today_str
            )
        db.session.add(investment)
        db.session.commit()
    wallets_n = [wallet for wallet in cw.user_actions if wallet.name == n]
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

@flask_app.route("/show_wallets/")
@login_required
def show_wallets():
    cw = Wallet(current_user.username)
    context = {
        "stock_date" : cw.stock_date,
        "wallets" : cw.user_wallets,
        "user" : current_user.username
    }
    return render_template("show.html", context=context)

if __name__ == '__main__':
    flask_app.run(debug=True)