from celery import Celery
import time
from datetime import datetime, timedelta
import requests
import csv

celery = Celery(
    'tasks',
    broker='sqla+sqlite:///celery.db',
	backend='db+sqlite:///celery_results.db'
	)

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
def get_AV_stock(symbols):
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
    return user_stock
