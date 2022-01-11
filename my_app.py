from flask_creator import flask_app
from flask import render_template, redirect, url_for, request
from tasks import download_AV_stock_symbols, get_AV_stock, update_db, save_plot_all, save_plot_wallets
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
    all_values = {}
    wallets_values = {}
    wallets_plot_data = []
    stock_by_date = Stock.query.filter_by(date=cw.stock_date).all()
    stock = Stock.query.all()
    if stock and cw.stock_date != '0000-00-00':
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
                wallet_plot_data = cw.wallet_plot_data(cw.user_wallets[f'{name}'], wallet_start_date)
                wallets_plot_data.append(wallet_plot_data)
                if wallets_plot_data:
                    save_plot_wallets.delay(wallets_plot_data, wallets_values, name, cw.stock_date, cw.username)
                cw.del_prev_plot_user(wallet_start_date, cw.today, current_user.username, name)
    context = {
        "stock_date" : cw.stock_date,
        "user_wallets" : cw.user_wallets,
        "user" : current_user.username,
    }
    if request.method == "POST":
        isoweekdays = [2, 3, 4, 5, 6]
        update_date = str(datetime.today().date() - timedelta(days=1))
        if datetime.isoweekday(datetime.today()) in isoweekdays and cw.symbols_to_update:
            user_stock = get_AV_stock.delay(cw.symbols_to_update, update_date).wait()
            for symbol, price in user_stock.items():
                user_stock[symbol] = price.wait()
            if user_stock:
                update_db.delay(update_date, user_stock, current_user.username)
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
            start_date = str(cw.today - timedelta(days=1))
            )
        db.session.add(investment)
        db.session.commit()
    user_actions = UsersActions.query.filter_by(user=current_user.username).all()
    wallets_n = [wallet for wallet in user_actions if wallet.name == n]
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

@flask_app.route("/show_wallets/", methods=["GET", "POST"])
@login_required
def show_wallets():
    cw = Wallet(current_user.username)
    n = request.form.get('name')
    if n:
        UsersActions.query.filter_by(name=n).delete()
        db.session.commit()
        os.remove(f'static/{cw.stock_date}_{current_user.username}_{n}.jpg')
        os.remove(f'static/{cw.stock_date}_{current_user.username}_all.jpg')
        return redirect(url_for('show_wallets'))
    context = {
        "stock_date" : cw.stock_date,
        "wallets" : cw.user_wallets,
        "user" : current_user.username
    }
    return render_template("show.html", context=context)

# if __name__ == '__main__':
#     flask_app.run(debug=True)