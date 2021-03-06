from celery import Celery
from flask_creator import flask_app
from api_key import api_key
import requests
import csv
from db_creator import init_db
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta

celery = Celery(
    'tasks',
    broker='sqla+sqlite:///celery.db',
	backend='db+sqlite:///celery_results.db'
	)

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

@celery.task(autoretry_for=(Exception,), default_retry_delay=60)
def update(symbols_to_update, update_date, username):
    updated_symbols = [item.symbol for item in Stock.query.filter_by(date=update_date).all()]
    for symbol in symbols_to_update:
        if symbol not in updated_symbols:
            AV_api_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}'
            price = requests.get(AV_api_url).json()['Time Series (Daily)'][update_date]['4. close']
            print(f'((({symbol}, {price})))')
            stock = Stock(
                symbol = symbol,
                price = price,
                date = update_date,
                user = username
                )
            db.session.add(stock)
        db.session.commit()

@celery.task
def save_plot_all(plot_data, values, username):
    plt.style.use('dark_background')
    plt.style.use('./static/presentation.mplstyle')
    fig, ax = plt.subplots()
    with plt.style.context('dark_background'):
        ax.plot(plot_data[0], plot_data[1], 'b')
        ax.axis('off')
    fig.text(0.05, 0.93, f'total', color='white', size=25,  fontweight='bold')
    fig.text(0.80, 0.93, f'''{values['wallet_perc']} %''', 
        color='white', size=15, fontweight='bold')
    fig.text(0.05, 0.85, f'''$ {values['wallet_invest']}''', 
        color='white', size=15, fontweight='bold')
    fig.text(0.05, 0.05, f'''{plot_data[0][0]}''', 
        color='white', size=15, fontweight='bold')
    fig.text(0.75, 0.05, f'''{plot_data[0][-1]}''', 
        color='white', size=15, fontweight='bold')
    if values['wallet_profit'] >= 0:
        fig.text(0.5, 0.5, f'''{values['wallet_profit']} $''', 
            color='#00FF00', fontweight='bold', ha='center', va='center', size=50)
    else: 
        fig.text(0.5, 0.5, f'''{values['wallet_profit']} $''', 
            color='orangered', fontweight='bold', ha='center', va='center', size=50)
    fig.savefig(f'static/{username}_all.png')

@celery.task
def save_plot_wallets(wallets_data, values, name, username):
    for data in wallets_data:
        for i in range(1, len(data[0])-1):
            data[0][i] = i
        plt.style.use('dark_background')
        plt.style.use('./static/presentation.mplstyle')
        fig, ax = plt.subplots()
        with plt.style.context('dark_background'):
            ax.plot(data[0], data[1], 'b')
            ax.axis('off')
        fig.text(0.05, 0.93, f'{name}', color='white', size=25,  fontweight='bold')
        fig.text(0.75, 0.93, f'''{values[f'{name}']['wallet_perc']} %''', 
            color='white', size=15, fontweight='bold')
        fig.text(0.05, 0.85, f'''$ {values[f'{name}']['wallet_invest']}''', 
            color='white', size=15, fontweight='bold')
        fig.text(0.05, 0.05, f'''{data[0][0]}''', 
            color='white', size=15, fontweight='bold')
        fig.text(0.75, 0.05, f'''{data[0][-1]}''', 
            color='white', size=15, fontweight='bold')
        if values[f'{name}']['wallet_profit'] >= 0:
            fig.text(0.5, 0.5, f'''{values[f'{name}']['wallet_profit']} $''', 
                color='#00FF00', fontweight='bold', ha='center', va='center', size=50)
        else: 
            fig.text(0.5, 0.5, f'''{values[f'{name}']['wallet_profit']} $''', 
            color='orangered', fontweight='bold', ha='center', va='center', size=50)
        fig.savefig(f'static/{username}_{name}.png')