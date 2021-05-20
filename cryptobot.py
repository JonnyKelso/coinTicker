#cryptobot
# requires python 3.8.7
#------------
import csv
import config
import time
from datetime import date       
from enum import Enum           
import os
import sys
from decimal import *
import math

#Binance
from binance.client import Client
from binance import exceptions

#Discord
import requests
from discord import Webhook, RequestsWebhookAdapter

import json
class State(Enum):
    ACTIVE      = 1
    INACTIVE    = 2
    
class DiscordHelper:
    webhook = None
    state = State.INACTIVE

    def __init__(self, url):
        self.webhook = Webhook.from_url(url, adapter=RequestsWebhookAdapter())

    def sendDiscordMsg(self, message):
        if self.state == State.ACTIVE:
            self.webhook.send(message)

    def SetState(self, state):
        self.state = state

class BinanceHelper:
    client = None
    #currentBalance = -1.0
    instrument_names = []

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
        coinBalance = 0.0
        try:
            response = self.client.get_account()  
        except Exception as e: # exceptions.BinanceAPIException as err:
            print(f"Binance exception during getAccountBalanceForSymbol: \n {e}") 
            return None
        else:
            #print("getAccountBalanceForSymbol")
            for balance in response['balances']:
                if balance['asset'] == symb :
                    #print(f"asset = {symb}, num = {balance['free']}")
                    if Decimal(balance['free']) > 0.0:
                        coinBalance = Decimal(balance['free'])
        return coinBalance

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

    def getAllInstrumentNames(self):
        prices = self.getPrices()
        for price in prices:
            #print(price)
            self.instrument_names = price['symbol']
        return self.instrument_names


class Instrument:
    def __init__(self, symbol, pairs, notifyBalanceThresholdDelta, notifyPriceThresholdDelta):
        self.symbol         = symbol
        self.pairs          = pairs
        self.cointTotal     = 0.0
        self.balanceUSDT    =   {
                                    'balance': Decimal(0.0),
                                    'min':Decimal(0.0),
                                    'max':Decimal(0.0)
                                }
        self.balanceGBP     =   {
                                    'balance':Decimal(0.0),
                                    'min':Decimal(0.0),
                                    'max':Decimal(0.0)
                                }
        self.coinPriceUSDT                  = Decimal(0.0)
        self.coinPriceGBP                   = Decimal(0.0)
        self.notifyBalanceThresholdDelta    = Decimal(notifyBalanceThresholdDelta)
        self.notifyBalanceThreshold         = Decimal(0.0)
        self.notifyPriceThresholdDelta      = Decimal(notifyPriceThresholdDelta)
        self.notifyPriceThreshold           = Decimal(0.0)
        self.distanceToPriceThreshold       = Decimal(0.0)

    def __str__(self):
        return (f"{self.symbol},                        \
                    {self.pairs},                       \
                    {self.balanceUSDT},                 \
                    {self.balanceGBP},                  \
                    {self.coinPriceUSDT},               \
                    {self.coinPriceGBP},                \
                    {self.notifyBalanceThresholdDelta}, \
                    {self.notifyBalanceThreshold},      \
                    {self.notifyPriceThresholdDelta},   \
                    {self.notifyPriceThreshold},        \
                    {self.distanceToPriceThreshold}")

class Account:
    def __init__(self):
        self.instruments = []
        self.baseCurrency = "GBP"

def calcDisplayMarkerPosition(instrument):
#    global priceBaseline
    adjusted_Coin_price = int(instrument.coinPriceUSDT * 1000.0) # in tenths of a cent
    if instrument.priceBaseline == 0:
        instrument.priceBaseline = adjusted_Coin_price / 10
        instrument.priceBaseline = instrument.priceBaseline * 10
    #print(f"{displayLineLength}, {adjusted_Coin_price}, {priceBaseline}")
    return (displayLineLength / 2) + (adjusted_Coin_price - instrument.priceBaseline)

def printLogMessage(message):
    msg = f"{getTime()}, {math.trunc(time.time())}, {message}"
    print(msg)

def writeData(writer, message):
    msg = f"{time.time()}, {getTime()}, {message}"
    writer.writerow([msg])

def getTime():
    t = time.localtime()
    #return time.strftime("%H:%M:%S", t)
    return time.strftime("%b %d %Y %H:%M:%S", t)
    
def getDateStr():
    d = date.today()
    t = time.localtime()
    return (f"{d.isoformat()}T{time.strftime('%H%M%S', t)}")

def getCoinPriceInUSDT(instrument):
    # get coin price
    # requires that instrument contains a list of coin pairs required to convert from starting symbol to USDT
    # e.g. for DOGEBTC, this would be ["DOGEBTC","BTCUSDT"]

    # number of coins for getting initial price
    conversionPrice = Decimal(1.0)
    
    for pair in instrument.pairs:
    #if symbolPair['2'] == baseCurrency:
     #   print(f"using base currency {baseCurrency} already in {symbolPair['1']}{symbolPair['2']}")
        coin_price = binHelper.getPrice(f"{pair}")       # returns a price object
        coin_bid_price = Decimal(coin_price['bidPrice'])      # extract the bidPrice from the object
        conversionPrice = conversionPrice * coin_bid_price
        #print(f"coin_bid_price:{coin_bid_price} for {pair}")
    coin_price_in_USDT = conversionPrice
    return coin_price_in_USDT
   

def getNotifyPriceThreshold(currentPrice):
    #global notifyPriceThreshold
    adj_price = int(currentPrice * 100)
    return Decimal(adj_price) / 100.0

def printCoinBalances(accountBalances):
     #:{str('total $').rjust(10,' ')}:{str('total £').rjust(10,' ')}")
    #print(f"{str('coin').rjust(4,' ')}:{str('total').rjust(10,' ')}")
    print("Number of coins:")
    for balance in accountBalances['balances']:
        if Decimal(balance['free']) > 0.0:
            asset = balance['asset']
            totalbalance = Decimal(balance['free'])
            print(f"{asset.rjust(4,' ')}:{str(totalbalance).rjust(10,' ')}")
        
        


def printBalances(accountBalances):
    pass
    # print(f"{str('coin').rjust(4,' ')}:{str('total').rjust(10,' ')}:{str('total $').rjust(10,' ')}:{str('total £').rjust(10,' ')}")
    # for balance in accountBalances['balances']:
    #     if float(balance['free']) > 0.0:
    #         asset = balance['asset']
    #         totalbalance = float(balance['free'])
    #         pairUSDT = f"{asset}USDT"
    #         pairGBP = f"{asset}GBP"
    #         totalBalanceUSDT = totalbalance * getCoinPrice(pairUSDT, 'USDT')
    #         totalBalanceGBP = totalbalance * getCoinPrice(pairGBP, 'GBP')
    #         print(f"{asset.rjust(4,' ')}:{rightJustifyString(totalbalance, 10)}:{rightJustifyString(totalBalanceUSDT,10)}:{rightJustifyString(totalBalanceGBP,10)}")
           

def rightJustifyString(value, totalLength):
    return str(f"{value:.2f}")

def CheckNotifyAboutPrice(instrument):
    if(CheckPrice == False):
        return False
    price = Decimal(instrument.coinPriceUSDT)
    if instrument.notifyPriceThreshold == 0.0  :
        instrument.notifyPriceThreshold = Decimal(instrument.notifyPriceThresholdDelta)

    # if balance > balanceThreshold + notifyThreshold, then notify via Discord
    if price > 0.0 : # 1.0:
        upperThreshold = Decimal(instrument.notifyPriceThreshold + instrument.notifyPriceThresholdDelta)
        if price > upperThreshold :
            instrument.notifyPriceThreshold = Decimal((price // instrument.notifyPriceThresholdDelta) * instrument.notifyPriceThresholdDelta) + instrument.notifyPriceThresholdDelta
            return True
            #instrument.balanceThreshold = (instrument.balanceThreshold + instrument.notifyBalanceThreshold)

        lowerThreshold = Decimal(instrument.notifyPriceThreshold - instrument.notifyPriceThresholdDelta)
        if price < lowerThreshold :
            instrument.notifyPriceThreshold = Decimal(price // instrument.notifyPriceThresholdDelta) * instrument.notifyPriceThresholdDelta
            return True
    return False

def CheckNotifyAboutBalance(instrument):
    balance = Decimal(instrument.balanceGBP['balance'])
    if instrument.notifyBalanceThreshold == 0.0 :
        instrument.notifyBalanceThreshold = Decimal(instrument.notifyBalanceThresholdDelta)
    
    # if balance > balanceThreshold + notifyThreshold, then notify via Discord
    if balance > 0.0: # 1.0:
        upperThreshold = Decimal(instrument.notifyBalanceThreshold + instrument.notifyBalanceThresholdDelta)
        if balance > upperThreshold :
            # find highest multiple of threshold delta below current balance, then add another delta
            instrument.notifyBalanceThreshold = Decimal((balance // instrument.notifyBalanceThresholdDelta) * instrument.notifyBalanceThresholdDelta) + instrument.notifyBalanceThresholdDelta
            return True
            #instrument.balanceThreshold = (instrument.balanceThreshold + instrument.notifyBalanceThreshold)

        lowerThreshold = Decimal(instrument.notifyBalanceThreshold - instrument.notifyBalanceThresholdDelta)        
        if balance < lowerThreshold :
            # find highest multiple of threshold delta below current balance
            instrument.notifyBalanceThreshold = Decimal(balance // instrument.notifyBalanceThresholdDelta) * instrument.notifyBalanceThresholdDelta
            return True
    return False

def NotifyAboutPrice(writer, discordHelper, oldThreshold, instrument):
    movement = "DOWN"
    if instrument.coinPriceUSDT > oldThreshold:
        movement = "UP"
    msg = (f"{instrument.symbol.rjust(4,' ')} price {movement} from {oldThreshold} to {instrument.coinPriceUSDT.quantize(Decimal('1.000'))}, new threshold at {instrument.notifyPriceThreshold.quantize(Decimal('1.000'))}")
    printLogMessage(msg)
    discordHelper.sendDiscordMsg(f"@here {getTime()} {msg}")

def NotifyAboutBalance(writer, discordHelper, oldThreshold, instrument):
    movement = "DOWN"
    if instrument.balanceGBP['balance'] > oldThreshold:
        movement = "UP"
    msg = (f"{instrument.symbol.rjust(4,' ')} balance {movement} from {oldThreshold} to {instrument.balanceGBP['balance'].quantize(Decimal('1.00'))}, new threshold at {instrument.notifyBalanceThreshold.quantize(Decimal('1.00'))}")
    printLogMessage(msg)
    discordHelper.sendDiscordMsg(f"@here {getTime()} {msg}")
    

if __name__ == '__main__':
    priceBaseline           = 0
    displayLineLength       = 100           # for display only - the number of character spaces used to display price marker
    sleepDelayMin           = 15             # time between querying the binance API
    CheckPrice = True
    useDiscord = True

    binHelper = BinanceHelper(config.API_KEY, config.API_SECRET)
    if binHelper is None:
        sys.exit("Could not initialise Binance API, exiting.")

    disHelper = DiscordHelper(config.DISCORD_WEBHOOK_URL)
    if useDiscord :
        disHelper.SetState(State.ACTIVE)

    # set Decimal precision
    getcontext().prec = 15

    account = Account()
    # Define instruments to track, and a list of instruments required to convert to a base of USDT
    # final conversion of USDT to GBP will be done later.
    # the notifyBalance threshold is in GBP and notifyPrice threshold is in USDT
    account.instruments.append(Instrument("DOGE", ["DOGEUSDT"], 500, 0.1))
    account.instruments.append(Instrument("BTC", ["BTCUSDT"], 500, 1000))
    account.instruments.append(Instrument("ETH", ["ETHBTC", "BTCUSDT"], 250, 250))

    balances = binHelper.getAccountBalances()
    printCoinBalances(balances)
    
    with open("data_file.json", "w") as write_file:
        with open(f"cryptobot_log_{getDateStr()}.csv", 'w', newline ='') as csv_file :
            data_writer = csv.writer(csv_file, delimiter=',') 
            printLogMessage(f"New run starting at {getDateStr()}") 
            print("starting loop")
            while(True):
                
                for instr in account.instruments:
                    # get number of coins
                    coin_total = binHelper.getAccountBalanceForSymbol(instr.symbol)
                    if coin_total is None:
                        print("couldn't get balance")
                        continue
                    instr.coinTotal = coin_total
                    if instr.coinTotal == 0.0:
                        continue
                    # get the coin value in BTC (used as stepping stone to calc value in GBP)
                    instr.coinPriceUSDT = getCoinPriceInUSDT(instr)

                    # calc price in GBP
                    GBPUSDT_price_obj = binHelper.getPrice("GBPUSDT")
                    GBPUSDT_price = Decimal(GBPUSDT_price_obj['bidPrice'])      # extract the bidPrice from the object
                    instr.coinPriceGBP = instr.coinPriceUSDT / GBPUSDT_price

                    # set current and min/max balance values in GBP
                    instr.balanceGBP['balance'] = instr.coinPriceGBP * instr.coinTotal
                    instr.balanceGBP['max'] = max(instr.balanceGBP['balance'], instr.balanceGBP['max'])
                    if( instr.balanceGBP['min'] == 0.0) :
                        instr.balanceGBP['min'] = instr.balanceGBP['balance']
                    else :
                        instr.balanceGBP['min'] = min(instr.balanceGBP['balance'], instr.balanceGBP['min'])

                    # set current and min/max balance values in USD
                    instr.balanceUSDT['balance'] = instr.coinPriceUSDT * instr.coinTotal
                    instr.balanceUSDT['max'] = max (instr.balanceUSDT['balance'], instr.balanceUSDT['max'])
                    if ( instr.balanceUSDT['min'] == 0 ) :
                        instr.balanceUSDT['min'] = instr.balanceUSDT['balance']
                    else :
                        instr.balanceUSDT['min'] = min (instr.balanceUSDT['balance'], instr.balanceUSDT['min'])

                    
                    # set threshold from which to measure price movement.
                    currentThreshold = instr.notifyPriceThreshold
                    if(CheckNotifyAboutPrice(instr)):
                        NotifyAboutPrice(data_writer, disHelper, currentThreshold, instr)
                    currentThreshold = instr.notifyBalanceThreshold
                    if(CheckNotifyAboutBalance(instr)):
                        NotifyAboutBalance(data_writer, disHelper, currentThreshold, instr)

    # adjust (quantize) price values only for display
                    justCoinPriceGBP = str(Decimal(instr.coinPriceGBP).quantize(Decimal('1.000')))
                    justCoinPriceUSDT = str(Decimal(instr.coinPriceUSDT).quantize(Decimal('1.000')))
                    justCoinTotal = str(Decimal(instr.coinTotal).quantize(Decimal('1.00000000')))
                    justCoinBalance = str(Decimal(instr.balanceGBP['balance']).quantize(Decimal('1.00')))
                    # log to screen
                    #printLogMessage(data_writer, f"{instr.symbol.rjust(4,' ')} Price £:{justCoinPriceGBP.rjust(15,' ')}, Price $:{justCoinPriceUSDT.rjust(15,' ')}, Total coins:{justCoinTotal.rjust(15,' ')}, Upper Thr: { instr.notifyBalanceThreshold + instr.notifyBalanceThresholdDelta}, Lower Thr: { instr.notifyBalanceThreshold - instr.notifyBalanceThresholdDelta}, Balance £:{justCoinBalance.rjust(10,' ')}")
                    printLogMessage(f"{instr.symbol.rjust(4,' ')} Price £:{justCoinPriceGBP.rjust(15,' ')}, Price $:{justCoinPriceUSDT.rjust(15,' ')}, Total coins:{justCoinTotal.rjust(15,' ')}, Upper Thr: { str(instr.notifyBalanceThreshold + instr.notifyBalanceThresholdDelta).rjust(5,' ')}, Lower Thr: { str(instr.notifyBalanceThreshold - instr.notifyBalanceThresholdDelta).rjust(5,' ')}, Balance £:{justCoinBalance.rjust(10,' ')}")


                    # print balance line
                    msg = f"{instr.symbol} : {instr.coinPriceUSDT.quantize(Decimal('1.000'))} : {instr.balanceGBP['min'].quantize(Decimal('1.00'))} : {instr.balanceGBP['max'].quantize(Decimal('1.00'))} : {instr.balanceGBP['balance'].quantize(Decimal('1.00'))}"#round up == false
                    writeData(data_writer, [msg])

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
