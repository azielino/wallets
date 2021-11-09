from flask import Flask, render_template, redirect, request
from flask.helpers import url_for
from wallets import Wallet
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
    name = db.Column(db.String(80), unique=False, nullable=False)
    symbol = db.Column(db.String(20), unique=False, nullable=False)
    price = db.Column(db.Float, unique=False, nullable=False)
    quantity = db.Column(db.Integer, unique=False, nullable=False, server_default="", default="")


class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField("Register")
    def validate_username(self, username):
        existing_user_name = User.query.filter_by(
            username=username.data).first()
        if existing_user_name:
            raise ValidationError(
                "Ta nazwa użytkownika już istnieje. Proszę wybrać inną nazwę.")


class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(
        min=4, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField("Login")


db.create_all()

w0 = Wallet(0,'')
symbols = w0.symbols_list

@app.route("/")
def start():
    return render_template("start.html")

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

@app.route("/rgister/", methods=['GET', 'POST'])
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
    context = {
        "stock_date" : w0.stock_date,
        "wallets_invest" : w0.wallet_invest,
        "wallets_profit" : w0.wallet_profit,
        "wallets_perc" : w0.wallet_perc,
        "wallets" : wallets
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
        stock = StockData(
            name = n,
            symbol = s,
            price = w,
            quantity = q
            )
        db.session.add(stock)
        db.session.commit()
    wallet_n = db.session.query(StockData).filter(StockData.name==n).all()
    context = {
        "stock_date" : w0.stock_date,
        "symbols" : symbols,
        "wallet_n" : wallet_n,
        "number" : n,
        "symbol" : s,
        "price" : w,
        "quantity" : q
    }
    return render_template("wallet.html", context=context)

@app.route("/show_wallets/")
@login_required
def show_wallets():
    wallets = {}
    for item in db.session.query(StockData).all():
        wallets[item.name] = db.session.query(StockData).filter(StockData.name==item.name).all()
    context = {
        "stock_date" : w0.stock_date,
        "wallets" : wallets 
    }
    return render_template("show.html", context=context)

if __name__ == '__main__':
    app.run(debug=True)
