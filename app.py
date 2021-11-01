from flask import Flask, render_template, request
from wallets import Wallet

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
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
    return render_template("index.html", context=context)

@app.route("/test/", methods=["GET", "POST"])
def test():
    return render_template("test.html")