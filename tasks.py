from celery import Celery
from flask_creator import flask_app
import time
from datetime import datetime, timedelta
import requests
import csv
from db_creator import init_db
import matplotlib.pyplot as plt

celery = Celery(
    'tasks',
    broker='sqla+sqlite:///celery.db',
	backend='db+sqlite:///celery_results.db'
	)

Users, Stock, UsersActions, db = init_db(flask_app)

AV_KEY = '*********'
today = datetime.today()
today_str = f'{str(today.day)}-{str(today.month)}-{str(today.year)}'
today_iso = str(datetime.isoweekday(datetime.today()))

@celery.task
def download_AV_stock_symbols():
    CSV_URL = f'https://www.alphavantage.co/query?function=LISTING_STATUS&state=active&apikey={AV_KEY}'
    with requests.Session() as s:
        download = s.get(CSV_URL)
        decoded_content = download.content.decode('utf-8')
        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)
        del my_list[0]
        return [row[0] for row in my_list]

@celery.task
def get_AV_stock(symbols, username):
    weekend = {'1': 3, '7': 2}
    user_stock = {}
    for i, symbol in enumerate(symbols):
        AV_api_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        r = requests.get(AV_api_url)
        if today_iso in weekend:
            price = r.json()['Time Series (Daily)'][str(today.date()-timedelta(weekend[today_iso]))]['4. close']
        else:
            price = r.json()['Time Series (Daily)'][str(today.date()-timedelta(1))]['4. close']
        user_stock[symbol] = price
        if (i + 1) % 5 == 0 and (i + 1) != len(symbols):
            time.sleep(58)
    for symbol, price in user_stock.items():
        stock = Stock(
            symbol = symbol,
            price = price,
            date = today_str,
            user = username
            )
        db.session.add(stock)
    db.session.commit()

@celery.task
def save_plot_all(plot_data, values, stock_date, username):
    plt.style.use('dark_background')
    plt.style.use('./static/presentation.mplstyle')
    fig, ax = plt.subplots()
    with plt.style.context('dark_background'):
        ax.plot(plot_data[0], plot_data[1], 'b-o')
        ax.set_ylim(0, values['wallet_invest'])
        ax.yaxis.set_major_formatter('${x:1.1f}')
        ax.yaxis.set_tick_params(which='major', labelcolor='green',
            labelleft=True, labelright=False)
    fig.text(0.35, 0.65, f'Całość', color='white', size=25,  fontweight='bold')
    fig.text(0.75, 0.93, f'''wynik  {values['wallet_perc']} %''', 
        color='white', size=12, fontweight='bold')
    fig.text(0.05, 0.93, f'''kapitał ${values['wallet_invest']}''', 
        color='white', size=12, fontweight='bold')
    if values['wallet_profit'] >= 0:
        fig.text(0.5, 0.5, f'''{values['wallet_profit']} $''', 
            color='#00FF00', fontweight='bold', ha='center', va='center', size=35)
    else: 
        fig.text(0.5, 0.5, f'''{values['wallet_profit']} $''', 
            color='orangered', fontweight='bold', ha='center', va='center', size=35)
    fig.savefig(f'static/{stock_date}_{username}_all.jpg')

@celery.task
def save_plot_wallets(wallets_data, values, name, stock_date, username):
    for data in wallets_data:
        for i in range(1, len(data[0])-1):
            data[0][i] = i
        plt.style.use('dark_background')
        plt.style.use('./static/presentation.mplstyle')
        fig, ax = plt.subplots()
        with plt.style.context('dark_background'):
            ax.plot(data[0], data[1], 'b-o')
            ax.set_ylim(0, values[f'{name}']['wallet_invest'])
            ax.yaxis.set_major_formatter('${x:1.1f}')
            ax.yaxis.set_tick_params(which='major', labelcolor='green',
                labelleft=True, labelright=False)
        fig.text(0.35, 0.65, f'{name}', color='white', size=25,  fontweight='bold')
        fig.text(0.75, 0.93, f'''{values[f'{name}']['wallet_perc']} %''', 
            color='white', size=12, fontweight='bold')
        fig.text(0.05, 0.93, f'''${values[f'{name}']['wallet_invest']}''', 
            color='white', size=12, fontweight='bold')
        if values[f'{name}']['wallet_profit'] >= 0:
            fig.text(0.5, 0.5, f'''{values[f'{name}']['wallet_profit']} $''', 
                color='#00FF00', fontweight='bold', ha='center', va='center', size=35)
        else: 
            fig.text(0.5, 0.5, f'''{values[f'{name}']['wallet_profit']} $''', 
            color='orangered', fontweight='bold', ha='center', va='center', size=35)
        fig.savefig(f'static/{stock_date}_{username}_{name}.jpg')