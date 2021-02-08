#cryptobot
#------------
import csv
import config
import time
from datetime import date
from enum import Enum

#Binance
from binance.client import Client
from binance import exceptions

#Discord
import requests
from discord import Webhook, RequestsWebhookAdapter

class State(Enum):
    ACTIVE      = 1
    INACTIVE    = 2
    
class DiscordHelper:
    webhook = None
    state = State.ACTIVE

    def __init__(self, url):
        self.webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

    def sendDiscordMsg(self, message):
        if self.state == State.ACTIVE:
            self.webhook.send(message)

    def SetState(self, state):
        self.state = state

class BinanceHelper:
    client = None
    currentBalance = -1.0

    def __init__(self, api_key, api_secret):
        self.client = Client(api_key, api_secret)
    
    def getPrices(self):
        return self.client.get_all_tickers()

    def getPrice(self, symb):
        try:
            price = self.client.get_ticker(symbol=symb)
        except exceptions.BinanceAPIException as err:
            print(f"Exception: {err}")
            price = None
        return price

    def getAccountBalances(self, symb):
        response = self.client.get_account()  
        for balance in response['balances']:
            if balance['asset'] == symb :
                if float(balance['free']) > 0.0:
                    self.currentBalance = float(balance['free'])
        return self.currentBalance

class Account:
    def __init__(self, symbol=None, pair=None, balance=0.0, minBalance=999999.0, maxBalance=0.0):
        self.symbol         = symbol
        self.pair           = pair
        self.balance        = balance
        self.minBalance     = minBalance
        self.maxBalance     = maxBalance

def calcDisplayMarkerPosition(coinPrice):
    global priceBaseline
    adjusted_Coin_price = int(coinPrice * 1000.0) # in tenths of a cent
    if priceBaseline == 0:
        priceBaseline = adjusted_Coin_price / 10
        priceBaseline = priceBaseline * 10
    #print(f"{displayLineLength}, {adjusted_Coin_price}, {priceBaseline}")
    return (displayLineLength / 2) + (adjusted_Coin_price - priceBaseline)

def printBalanceLine(logfile_writer, symbol, currentCoinPriceGBP, oneCoinInUSDT, accountBalance):
    # convert a current coin price from something like 0.00000181 to 81, 
    # so we can use that value to draw a little scale glyph from 0-100.
    marker_pos = calcDisplayMarkerPosition(oneCoinInUSDT)
    adjusted_coin_price = int(oneCoinInUSDT * 10000)
    adjusted_coin_price = adjusted_coin_price / 10 
    msg = f"{getTime()}: {symbol} : {oneCoinInUSDT:.4f} : {round(accountBalance.minBalance)} : {round(accountBalance.maxBalance)} : {round(accountBalance.balance)} : {str('|').rjust(int(marker_pos),' ')}"#round up == false
    print(msg)
    logfile_writer.writerow([msg])

def printLogMessage(message, writer):
    print(message)
    writer.writerow([message])

def getTime():
    t = time.localtime()
    return time.strftime("%H:%M:%S", t)
    
def getDateStr():
    d = date.today()
    t = time.localtime()
    return (f"{d.isoformat()}T{time.strftime('%H%M%S', t)}")

def getCoinPrice(symbolPair, baseCurrency):
    # get coin price
    coin_price_btc = binHelper.getPrice(symbolPair)       # returns a price object
    coin_bid_price = float(coin_price_btc['bidPrice'])      # extract the bidPrice from the object

    if baseCurrency in symbolPair:
        return coin_bid_price
    else:
        # get value of secondary coin in GBP 
        # # TODO - extend to other coin pairs than xxxxBTC
        btc_gbp_price = binHelper.getPrice(f'BTC{baseCurrency}')            # returns a price object
        btc_gbp_bidPrice = float(btc_gbp_price['bidPrice'])     # extract the bidPrice from the object
        return (coin_bid_price * btc_gbp_bidPrice)


if __name__ == '__main__':
    priceBaseline           = 0
    displayLineLength       = 100           # for display only - the number of character spaces used to display price marker
    sleepDelayMin           = 1             # time between querying the binance API
    notifyBalanceThreshold  = 20.0          # how far the profit value should move in GBP before notifying
    balanceThresholdBase    = 0.0           # baseline profit value used to measure profit movement for notification purposes

    binHelper = BinanceHelper(config.API_KEY, config.API_SECRET)
    disHelper = DiscordHelper(config.DISCORD_WEBHOOK)
    account = Account()
    account.symbol = 'DOGE'
    account.pair ='DOGEBTC'

    with open(f"{account.pair}_log_{getDateStr()}.csv", 'w', newline ='') as csv_file :
        data_writer = csv.writer(csv_file, delimiter=',') 
        disHelper.sendDiscordMsg(f"New run starting at {getDateStr()}")   

        while(True):
            # get number of coins
            coin_balance = binHelper.getAccountBalances(account.symbol)

            # get the coin value in BTC (used as stepping stone to cal value in GBP)
            current_coin_price_GBP = getCoinPrice(account.pair, 'GBP')
            current_coin_price_USDT = getCoinPrice(account.pair, 'USDT')
            current_btc_price_USDT = getCoinPrice('BTCUSDT', 'USDT')

            # get current coin account value in GBP
            account.balance = current_coin_price_GBP * coin_balance

            if account.balance > account.maxBalance:
                account.maxBalance = account.balance
            if account.balance < account.minBalance:
                account.minBalance = account.balance
            
            if balanceThresholdBase == 0.0 :
                balanceThresholdBase = account.balance - (account.balance % 10)
                msg = f"init balance threshold to {balanceThresholdBase}"
                printLogMessage(msg, data_writer)
                disHelper.sendDiscordMsg(msg)
            if account.balance > (balanceThresholdBase + notifyBalanceThreshold) :
                balanceThresholdBase = (balanceThresholdBase + notifyBalanceThreshold)
                disHelper.sendDiscordMsg(f"@here UP {notifyBalanceThreshold} to {round(account.balance,2)}, new threshold at {balanceThresholdBase}")
            if account.balance < (balanceThresholdBase - notifyBalanceThreshold) :
                balanceThresholdBase = (balanceThresholdBase - notifyBalanceThreshold)
                disHelper.sendDiscordMsg(f"@here DOWN {notifyBalanceThreshold} to {round(account.balance,2)}, new threshold at {balanceThresholdBase}")
            
            # print current values to log
            printBalanceLine(data_writer, account.pair, current_coin_price_GBP, current_coin_price_USDT, account)

            time.sleep(sleepDelayMin * 60)


#---------------------------------------------------------------------------
#candles = client.get_klines(symbol='BTCUSDT', interval=Client.KLINE_INTERVAL_15MINUTE)
#csvfile = open('15minuites.csv', 'w', newline ='')
#candlestick_writer = csv.writer(csvfile, delimiter=',')
#for candlestick in candles:
#    print(candlestick)
#    candlestick_writer.writerow(candlestick)
#print(len(candles))
#wss://stream.binance.com/9443
#---------------------------------------------------------------------------