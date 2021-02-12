#cryptobot
#------------
import csv
import config
import time
from datetime import date       
from enum import Enum           
import os
import sys

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
        try:
            self.client = Client(api_key, api_secret)
        except Exception as e: #exceptions.BinanceAPIException as err:
            print(f"Binance exception during init: \n {e}") 
            self.client = None
    
    def getPrices(self):
        try:
            prices = self.client.get_all_tickers()
        except Exception as e: # exceptions.BinanceAPIException as err:
            print(f"Binance exception during getPrices: \n {e}") 
            prices = None
        return prices

    def getPrice(self, symb):
        try:
            price = self.client.get_ticker(symbol=symb)
        except Exception as e: # exceptions.BinanceAPIException as err:
            print(f"Binance exception during getPrice: \n {e}") 
            price = None
        return price

    def getAccountBalanceForSymbol(self, symb):
        try:
            response = self.client.get_account()  
        except Exception as e: # exceptions.BinanceAPIException as err:
            print(f"Binance exception during getAccountBalanceForSymbol: \n {e}") 
            self.currentBalance = None
        else:
            for balance in response['balances']:
                if balance['asset'] == symb :
                    if float(balance['free']) > 0.0:
                        self.currentBalance = float(balance['free'])
        return self.currentBalance

    def getAccountBalances(self):
        try:
            response = self.client.get_account()  
        except Exception as e: # exceptions.BinanceAPIException as err:
            print(f"Binance exception during getAccountBalances: \n {e}") 
            self.balances = None
        else:
            self.balances = response
            
            #for balance in response['balances']:
            #    if balance['asset'] == symb :
            #        if float(balance['free']) > 0.0:
            #            self.currentBalance = float(balance['free'])
        return self.balances

class Instrument:
    def __init__(self, symbol, pair):
        self.symbol         = symbol
        self.pair           = pair
        self.balanceUSDT    =   {
                                    'balance':0.0,
                                    'min':0.0,
                                    'max':0.0
                                }
        self.balanceGBP     =   {
                                    'balance':0.0,
                                    'min':0.0,
                                    'max':0.0
                                }
        self.coinPriceUSDT             = 0.0
        self.coinPriceGBP              = 0.0
        self.notifyBalanceThreshold     = 0.0
        self.balanceThresholdBase       = 0.0
        self.notifyPriceThreshold       = 0.0
        self.priceBaseline              = 0.0
        self.distanceToPriceThreshold   = 0.0

    def __str__(self):
        return (f"{self.symbol},                    \
                    {self.pair},                    \
                    {self.balanceUSDT},             \
                    {self.balanceGBP},              \
                    {self.coinPriceUSDT},           \
                    {self.coinPriceGBP},            \
                    {self.notifyBalanceThreshold},  \
                    {self.balanceThresholdBase},    \
                    {self.notifyPriceThreshold},    \
                    {self.distanceToPriceThreshold}")

class Account:
    def __init__(self):
        self.instruments = []

def calcDisplayMarkerPosition(instrument):
#    global priceBaseline
    adjusted_Coin_price = int(instrument.coinPriceUSDT * 1000.0) # in tenths of a cent
    if instrument.priceBaseline == 0:
        instrument.priceBaseline = adjusted_Coin_price / 10
        instrument.priceBaseline = instrument.priceBaseline * 10
    #print(f"{displayLineLength}, {adjusted_Coin_price}, {priceBaseline}")
    return (displayLineLength / 2) + (adjusted_Coin_price - priceBaseline)

def printBalanceLine(logfile_writer, instrument):
    # convert a current coin price from something like 0.00000181 to 81, 
    # so we can use that value to draw a little scale glyph from 0-100.
    marker_pos = calcDisplayMarkerPosition(instrument)
    adjusted_coin_price = int(instrument.coinPriceUSDT * 10000)
    adjusted_coin_price = adjusted_coin_price / 10 
    print(f"markerpos: {marker_pos}, adjusted_coin_price: {adjusted_coin_price}")
    msg = f"{getTime()}: {instrument.symbol} : {instrument.coinPriceUSDT:.4f} : {round(instrument.balanceGBP['min'])} : {round(instrument.balanceGBP['max'])} : {round(instrument.balanceGBP['balance'])} : {str('|').rjust(int(marker_pos),' ')}"#round up == false
    #print(msg)
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

def getNotifyPriceThreshold(currentPrice):
    #global notifyPriceThreshold
    adj_price = int(currentPrice * 100)
    return float(adj_price) / 100.0

def printBalances(accountBalances):
    print(f"{str('coin').rjust(4,' ')}:{str('total').rjust(10,' ')}:{str('total $').rjust(10,' ')}:{str('total £').rjust(10,' ')}")
    for balance in accountBalances['balances']:
        if float(balance['free']) > 0.0:
            asset = balance['asset']
            totalbalance = float(balance['free'])
            pairUSDT = f"{asset}USDT"
            pairGBP = f"{asset}GBP"
            totalBalanceUSDT = totalbalance * getCoinPrice(pairUSDT, 'USDT')
            totalBalanceGBP = totalbalance * getCoinPrice(pairGBP, 'GBP')
            print(f"{asset.rjust(4,' ')}:{rightJustifyString(totalbalance, 10)}:{rightJustifyString(totalBalanceUSDT,10)}:{rightJustifyString(totalBalanceGBP,10)}")
            

def rightJustifyString(value, totalLength):
    return str(f"{value:.2f}").rjust(totalLength,' ')
if __name__ == '__main__':
    priceBaseline           = 0
    displayLineLength       = 100           # for display only - the number of character spaces used to display price marker
    sleepDelayMin           = 1             # time between querying the binance API
    notifyBalanceThreshold  = 20.0          # how far the profit value should move in GBP before notifying
    balanceThresholdBase    = 0.0           # baseline profit value used to measure profit movement for notification purposes
    
    #API_KEY = os.getenv('BINANCE_API_KEY')
    #API_SECRET = os.environ.get('BINANCE_API_SECRET')
    #DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
    #print(API_KEY)
    #print(API_SECRET)
    #print(DISCORD_WEBHOOK_URL)
    #binHelper = BinanceHelper(str(API_KEY), str(API_SECRET))
    #disHelper = DiscordHelper(str(DISCORD_WEBHOOK_URL))
    binHelper = BinanceHelper(config.API_KEY, config.API_SECRET)
    if binHelper is None:
        sys.exit("Could not initialise Binance API, exiting.")
    disHelper = DiscordHelper(config.DISCORD_WEBHOOK_URL)


    account = Account()
    account.instruments.append(Instrument("DOGE", "DOGEUSDT"))
    account.instruments.append(Instrument("BTC", "BTCUSDT"))

    balances = binHelper.getAccountBalances()
    #print(balances['balances'])
    printBalances(balances)

    with open(f"cryptobot_log_{getDateStr()}.csv", 'w', newline ='') as csv_file :
        data_writer = csv.writer(csv_file, delimiter=',') 
        disHelper.sendDiscordMsg(f"New run starting at {getDateStr()}")   

        while(True):
            
            for instr in account.instruments:
                discordMsg = ""
                # get number of coins
                coin_balance = binHelper.getAccountBalanceForSymbol(instr.symbol)
                if coin_balance is None:
                    print("couldn't get balance")
                    continue
                # get the coin value in BTC (used as stepping stone to cal value in GBP)
                current_coin_price_GBP = getCoinPrice(instr.pair, 'GBP')
                if current_coin_price_GBP is None:
                    print("couldn't get price")
                    continue
                current_coin_price_USDT = getCoinPrice(instr.pair, 'USDT')
                if current_coin_price_USDT is None:
                    print("couldn't get price")
                    continue
                current_btc_price_USDT = getCoinPrice('BTCUSDT', 'USDT')
                if current_btc_price_USDT is None:
                    print("couldn't get price")
                    continue

                # get current coin account value in GBP
                instr.coinPriceUSDT = current_coin_price_USDT
                instr.coinPriceGBP = current_coin_price_GBP
                instr.balanceGBP['balance'] = current_coin_price_GBP * coin_balance
                instr.balanceUSDT['balance'] = current_coin_price_USDT * coin_balance
                #print(f"coin_balance:{coin_balance},\ncurrent_coin_price_GBP:{current_coin_price_GBP},\ncurrent_coin_price_USDT:{current_coin_price_USDT},\ncurrent_btc_price_USDT:{current_btc_price_USDT},\naccount.balance:{account.balance}")
                if instr.balanceGBP['balance'] > instr.balanceGBP['max']:
                    instr.balanceGBP['max'] = instr.balanceGBP['balance']
                if instr.balanceGBP['balance'] < instr.balanceGBP['min']:
                    instr.balanceGBP['min'] = instr.balanceGBP['balance']
                
                if instr.balanceThresholdBase == 0.0  and instr.balanceGBP['balance'] > 1.0:
                    instr.balanceThresholdBase = instr.balanceGBP['balance'] - (instr.balanceGBP['balance'] % 10)
                    msg = f"init balance threshold for {instr.symbol} to {instr.balanceThresholdBase}"
                    printLogMessage(msg, data_writer)
                    discordMsg += msg
                    #disHelper.sendDiscordMsg(msg)
                if instr.balanceGBP['balance'] > 1.0:
                    if instr.balanceGBP['balance'] > (instr.balanceThresholdBase + instr.notifyBalanceThreshold) :
                        instr.balanceThresholdBase = (instr.balanceThresholdBase + instr.notifyBalanceThreshold)
                        discordMsg += (f"@here UP {instr.notifyBalanceThreshold} to {round(instr.balanceGBP['balance'],2)}, new threshold at {instr.balanceThresholdBase}")
                        #disHelper.sendDiscordMsg(f"@here UP {notifyBalanceThreshold} to {round(account.balance,2)}, new threshold at {balanceThresholdBase}")
                    if instr.balanceGBP['balance'] < (instr.balanceThresholdBase - instr.notifyBalanceThreshold) :
                        instr.balanceThresholdBase = (instr.balanceThresholdBase - instr.notifyBalanceThreshold)
                        discordMsg += (f"@here DOWN {instr.notifyBalanceThreshold} to {round(instr.balanceGBP['balance'],2)}, new threshold at {instr.balanceThresholdBase}")
                        #disHelper.sendDiscordMsg(f"@here DOWN {notifyBalanceThreshold} to {round(account.balance,2)}, new threshold at {balanceThresholdBase}")
                
                if instr.notifyPriceThreshold == 0.0:
                    instr.notifyPriceThreshold = getNotifyPriceThreshold(current_coin_price_USDT)
                distanceToPriceThreshold = abs(current_coin_price_USDT - instr.notifyPriceThreshold)
                print(f"distanceToPriceThreshold:{distanceToPriceThreshold:.4f}")
                if distanceToPriceThreshold > 1.0:
                    discordMsg += (f"{instr.symb} reached {notifyPriceThreshold}, now at {current_coin_price_USDT}")
                    #disHelper.sendDiscordMsg(f"{account.symbol} reached {notifyPriceThreshold}, now at {current_coin_price_USDT}")
                    notifyPriceThreshold = getNotifyPriceThreshold(current_coin_price_USDT)

                # print current values to log
                print(instr)

                printBalanceLine(data_writer, instr)

            time.sleep(sleepDelayMin * 60)
            disHelper.sendDiscordMsg(discordMsg)


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