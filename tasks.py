from celery import Celery
from celery.schedules import crontab
from flask_creator import flask_app
from api_key import api_key
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

celery.conf.timezone = 'Europe/Warsaw'

Users, Stock, UsersActions, db = init_db(flask_app)

AV_KEY = api_key

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
def update_db(update_date, user_stock, username):
    for symbol, price in user_stock.items():
        print(f'((({symbol}, {price})))')
        stock = Stock(
            symbol = symbol,
            price = price,
            date = update_date,
            user = username
            )
        db.session.add(stock)
    db.session.commit()

@celery.task(autoretry_for=(Exception,), default_retry_delay=60)
def get_AV_price(AV_api_url, update_date):
    return requests.get(AV_api_url).json()['Time Series (Daily)'][update_date]['4. close']

@celery.task
def get_AV_stock(symbols_to_update, update_date):
    celery.conf.beat_schedule = {
        'test-every-10-seconds': {
            'task': 'tasks.get_AV_stock',
            'schedule': timedelta(seconds=10),
            'args': (symbols_to_update, update_date)
        },
    }
    user_stock = {}
    for symbol in symbols_to_update:
        AV_api_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
        user_stock[symbol] = get_AV_price.delay(AV_api_url, update_date)
    return user_stock

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