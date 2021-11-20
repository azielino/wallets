from celery import Celery
from app import Wallet
import requests
from datetime import timedelta

celery = Celery(
    'tasks',
    broker='sqla+sqlite:///celery.db',
	backend='db+sqlite:///celery_results.db'
	)

@celery.task
def download_AV_price(source): # Alpha Vantage API
    r = requests.get(source)
    weekend = {'1': 3, '7': 2}
    if Wallet.today_iso in weekend:
        return r.json()['Time Series (Daily)'][str(Wallet.today.date()-timedelta(weekend[Wallet.today_iso]))]['4. close']
    return r.json()['Time Series (Daily)'][str(Wallet.today.date()-timedelta(1))]['4. close']