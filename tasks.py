from celery import Celery
import time
from datetime import datetime, timedelta
import requests
import csv

AV_KEY = '***' # Alpha Vantage API

celery = Celery(
    'tasks',
    broker='sqla+sqlite:///celery.db',
	backend='db+sqlite:///celery_results.db'
	)

today = datetime.today()
today_str = f'{str(today.day)}-{str(today.month)}-{str(today.year)}'
today_iso = str(datetime.isoweekday(datetime.today()))

@celery.task
def set_user_symbols(username):
    user_symbols = set()
    user_actions = UsersActions.query.filter_by(user=username).all()
    if user_actions:
        return list({action.symbol for action in user_actions if action.symbol not in user_symbols})
    return user_symbols

@celery.task
def download_AV_stock_symbols(): # Alpha Vantage API
    CSV_URL = f'https://www.alphavantage.co/query?function=LISTING_STATUS&state=active&apikey={AV_KEY}'
    with requests.Session() as s:
        download = s.get(CSV_URL)
        decoded_content = download.content.decode('utf-8')
        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)
        del my_list[0]
        return [row[0] for row in my_list]

def download_AV_price(source): # Alpha Vantage API
    r = requests.get(source)
    weekend = {'1': 3, '7': 2}
    if today_iso in weekend:
        return r.json()['Time Series (Daily)'][str(today.date()-timedelta(weekend[today_iso]))]['4. close']
    return r.json()['Time Series (Daily)'][str(today.date()-timedelta(1))]['4. close']

@celery.task
def update_stock(user_symbols, username):
    today_stock = Stock.query.filter_by(date=today_str).all()
    today_stock_symbols = {obj.symbol for obj in today_stock}
    if today_stock_symbols:
        for symbol in today_stock_symbols:
            if symbol in user_symbols:
                user_symbols.remove(symbol)
    if user_symbols:
        i = 0
        for symbol in user_symbols:
            AV_api_url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={AV_KEY}' # Alpha Vantage API
            price = download_AV_price(AV_api_url) # Alpha Vantage API
            stock = Stock(
                symbol = symbol,
                price = price,
                date = today_str,
                user = username
                )
            db.session.add(stock)
            db.session.commit()
            i += 1
            if i % 5 == 0 and i != len(user_symbols):
                time.sleep(58) # Alpha Vantage API
        return True
    return False