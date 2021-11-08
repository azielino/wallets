from celery import Celery
from flask import Flask, render_template, request
from wallets import Wallet
from flask_sqlalchemy import SQLAlchemy

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery

app = Flask(__name__)
flask_app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wallets.db'
flask_app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379',
    CELERY_RESULT_BACKEND='redis://localhost:6379'
)

celery = make_celery(flask_app)

db = SQLAlchemy(app)

class StockData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=False, nullable=False)
    symbol = db.Column(db.String(20), unique=False, nullable=False)
    price = db.Column(db.Float, unique=False, nullable=False)
    quantity = db.Column(db.Integer, unique=False, nullable=False, server_default="", default="")

db.create_all()

w0 = Wallet(0,'')
symbols = w0.symbols_list

@celery.task()
def update_stock():
    w0 = Wallet(0,'')
    if w0.act_date != w0.stock_date:
        w0 = Wallet(0,'***')
        return '***'
    return ''

@app.route("/", methods=["GET", "POST"])
def home():
    api_key = update_stock()
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
    return render_template("index.html", context=context)

@app.route("/create_wallet/", methods=["GET", "POST"])
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
def show_wallets():
    wallets = {}
    for item in db.session.query(StockData).all():
        wallets[item.name] = db.session.query(StockData).filter(StockData.name==item.name).all()
    context = {
        "stock_date" : w0.stock_date,
        "wallets" : wallets 
    }
    return render_template("show.html", context=context)