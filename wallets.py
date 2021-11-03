from datetime import datetime, timedelta
import requests
import csv
import os

class Wallet:
    
    TAX = 0.19
    COMM_PERC = 0.0038

    def __init__(self, number, api_key):
        self.api_key = api_key
        self.number = str(number)
        self.wallets_amount = self.count_wallets()
        self.today = datetime.today()
        self.stock_date = ''
        self.today_stock_file_name = self.set_stock_file_name()
        self.today_iso = str(datetime.isoweekday(self.today))
        self.symbols_list = []
        self.companies_amount = self.symbols()
        self.wallet_income = round(float(), 2)
        self.wallet_invest = round(float(), 2)
        self.wallet_profit = self.get_wallet_profit(self.get_wallet(self.number), self.get_stock())
        self.wallet_perc = round((self.wallet_profit / self.wallet_invest) * 100, 1)

    def set_dol_c(self, y, z):
        if not y:
            y = 0
        if not z:
            z = 0
        if int(z) >= 0:
            y = float(y)
            if int(z) < 10:
                z = '0.0' + str(z)
            elif int(z) > 10:  
                O_z = '0.' + str(z)
                z = round(float(O_z), 2)
                z = str(z)[0 : 4]
            z = float(z)
        return str(y + z)

    def count_wallets(self):
        with os.scandir('investment') as it:
            i = 0
            for entry in it:
                if not entry.name.startswith('.') and entry.is_file():
                    i += 1
        return i

    def set_stock_file_name(self):
        if self.api_key:
            self.stock_date = f'{str(self.today.year)}-{str(self.today.month)}-{str(self.today.day)}'
            return f'stock/{str(self.today.year)}{str(self.today.month)}{str(self.today.day)}.csv'
        for i in range(0, 32):
            today = datetime.today() - timedelta(i)
            if os.path.exists(f'stock/{str(today.year)}{str(today.month)}{str(today.day)}.csv'):
                self.stock_date = f'{str(today.year)}-{str(today.month)}-{str(today.day)}'
                return f'stock/{str(today.year)}{str(today.month)}{str(today.day)}.csv'

    def set_api_url(self, symbol):
        return f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={self.api_key}'


    def get_wallet(self, number):
        if number == '0':
            return 'investment/wallets.csv'
        elif os.path.exists(f'investment/wallet_{number}.csv'):
            return f'investment/wallet_{number}.csv'
        return None

    def symbols(self):
        with open('investment/wallets.csv' , newline='') as file:
            wallet = csv.reader(file)
            for row in wallet:
                self.symbols_list.append(row[0])
        return len(self.symbols_list)

    def get_api(self, source):
        r = requests.get(source)
        weekend = {'1': 3, '7': 2}
        if self.today_iso in weekend:
            return r.json()['Time Series (Daily)'][str(self.today.date()-timedelta(weekend[self.today_iso]))]['4. close']
        return r.json()['Time Series (Daily)'][str(self.today.date()-timedelta(1))]['4. close']

    def stop(self, end_time):
        while end_time > datetime.now():
            pass

    def get_stock(self):  
        if self.today_stock_file_name and not os.path.exists(self.today_stock_file_name):
            with open(self.today_stock_file_name, 'a', newline='') as file:
                for nr in range(self.companies_amount):
                    nr += 1
                    if nr % 5 == 0:
                        xfive = nr
                        end_time = None
                        for i in range(xfive-6, xfive-1):
                            api_url = self.set_api_url(self.symbols_list[i+1])
                            file.write(f'{self.symbols_list[i+1]},{self.get_api(api_url)}\n')
                            if not end_time:
                                end_time = datetime.now() + timedelta(minutes=1)
                        self.stop(end_time)
                        continue
                    elif len(self.symbols_list) - nr == 0:
                        for i in range(xfive, len(self.symbols_list)):
                            api_url = self.set_api_url(self.symbols_list[i])
                            file.write(f'{self.symbols_list[i]},{self.get_api(api_url)}\n')
        return self.today_stock_file_name

    def get_wallet_profit(self, base_wallet, stock):
        if base_wallet and stock:
            with open(base_wallet, newline='') as file1:
                base1 = csv.reader(file1)
                for row1 in base1:
                    with open(stock, newline='') as file2:
                        wallet2 = csv.reader(file2)
                        for row2 in wallet2:
                            if row1[0] == row2[0]:
                                invest = float(row1[2]) * float(row1[1])
                                income = float(row1[2]) * float(row2[1])
                                self.wallet_invest += invest
                                self.wallet_income += income
            wallet_profit = self.wallet_income - self.wallet_invest
            wallet_profit *= (1 - self.TAX)
            wallet_profit -= (self.wallet_income * self.COMM_PERC)
            return round(wallet_profit, 2)
