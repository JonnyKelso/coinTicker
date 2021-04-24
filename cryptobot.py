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
from decimal import Decimal

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
                    if float(balance['free']) > 0.0:
                        coinBalance = float(balance['free'])
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
                                    'balance':0.0,
                                    'min':0.0,
                                    'max':0.0
                                }
        self.balanceGBP     =   {
                                    'balance':0.0,
                                    'min':0.0,
                                    'max':0.0
                                }
        self.coinPriceUSDT                  = 0.0
        self.coinPriceGBP                   = 0.0
        self.notifyBalanceThresholdDelta    = notifyBalanceThresholdDelta
        self.notifyBalanceThreshold         = 0.0
        self.notifyPriceThresholdDelta      = notifyPriceThresholdDelta
        self.notifyPriceThreshold           = 0.0
        self.distanceToPriceThreshold       = 0.0

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

def printBalanceLine(logfile_writer, instrument):
    # convert a current coin price from something like 0.00000181 to 81, 
    # so we can use that value to draw a little scale glyph from 0-100.
    #marker_pos = calcDisplayMarkerPosition(instrument)
    #adjusted_coin_price = int(instrument.coinPriceUSDT * 10000)
    #adjusted_coin_price = adjusted_coin_price / 10 
    #print(f"markerpos: {marker_pos}, adjusted_coin_price: {adjusted_coin_price}")
    #msg = f"{getTime()}: {instrument.symbol} : {instrument.coinPriceUSDT:.4f} : {round(instrument.balanceGBP['min'])} : {round(instrument.balanceGBP['max'])} : {round(instrument.balanceGBP['balance'])} : {str('|').rjust(int(marker_pos),' ')}"#round up == false
    msg = f"{getTime()}: {instrument.symbol} : {instrument.coinPriceUSDT:.4f} : {round(instrument.balanceGBP['min'])} : {round(instrument.balanceGBP['max'])} : {round(instrument.balanceGBP['balance'])}"#round up == false
    #print(msg)
    logfile_writer.writerow([msg])

def printLogMessage(writer, message):
    print(message)
    writer.writerow([message])

def getTime():
    t = time.localtime()
    return time.strftime("%H:%M:%S", t)
    
def getDateStr():
    d = date.today()
    t = time.localtime()
    return (f"{d.isoformat()}T{time.strftime('%H%M%S', t)}")

def getCoinPriceInUSDT(instrument):
    # get coin price
    # requires that instrument contains a list of coin pairs required to convert from starting symbol to USDT
    # e.g. for DOGEBTC, this would be ["DOGEBTC","BTCUSDT"]

    # number of coins for getting initial price
    conversionPrice = 1.0
    
    for pair in instrument.pairs:
    #if symbolPair['2'] == baseCurrency:
     #   print(f"using base currency {baseCurrency} already in {symbolPair['1']}{symbolPair['2']}")
        coin_price = binHelper.getPrice(f"{pair}")       # returns a price object
        coin_bid_price = float(coin_price['bidPrice'])      # extract the bidPrice from the object
        conversionPrice *= coin_bid_price
        #print(f"coin_bid_price:{coin_bid_price} for {pair}")
    coin_price_in_USDT = conversionPrice
    return coin_price_in_USDT
   

def getNotifyPriceThreshold(currentPrice):
    #global notifyPriceThreshold
    adj_price = int(currentPrice * 100)
    return float(adj_price) / 100.0

def printCoinBalances(accountBalances):
     #:{str('total $').rjust(10,' ')}:{str('total £').rjust(10,' ')}")
    #print(f"{str('coin').rjust(4,' ')}:{str('total').rjust(10,' ')}")
    print("Number of coins:")
    for balance in accountBalances['balances']:
        if float(balance['free']) > 0.0:
            asset = balance['asset']
            totalbalance = float(balance['free'])
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
    price = instrument.coinPriceUSDT
    if instrument.notifyPriceThreshold == 0.0  :
        instrument.notifyPriceThreshold = instrument.notifyPriceThresholdDelta
        #msg = f"set balance threshold for {instr.symbol} to {instr.balanceThreshold}"
        #printLogMessage(data_writer, msg)
        #disHelper.sendDiscordMsg(msg)

    # if balance > balanceThreshold + notifyThreshold, then notify via Discord
    if price > 0.0 : # 1.0:
        upperThreshold = (instrument.notifyPriceThreshold + instrument.notifyPriceThresholdDelta)
        if price > upperThreshold :
            instrument.notifyPriceThreshold = ((price // instrument.notifyPriceThresholdDelta) * instrument.notifyPriceThresholdDelta) + instrument.notifyPriceThresholdDelta
            return True
            #instrument.balanceThreshold = (instrument.balanceThreshold + instrument.notifyBalanceThreshold)

        lowerThreshold = (instrument.notifyPriceThreshold - instrument.notifyPriceThresholdDelta)
        if price < lowerThreshold :
            instrument.notifyPriceThreshold = (price // instrument.notifyPriceThresholdDelta) * instrument.notifyPriceThresholdDelta
            return True
            # msg = (f"@here {instrument.symbol} DOWN {instrument.notifyBalanceThreshold} to {round(instrument.balanceGBP['balance'],2)}, new threshold at {instrument.balanceThreshold}")
            # printLogMessage(data_writer, msg)
            # disHelper.sendDiscordMsg(msg)
    return False

def CheckNotifyAboutBalance(instrument):
    balance = instrument.balanceGBP['balance']
    if instrument.notifyBalanceThreshold == 0.0 :
        instrument.notifyBalanceThreshold = instrument.notifyBalanceThresholdDelta
        #msg = f"set balance threshold for {instr.symbol} to {instr.balanceThreshold}"
        #printLogMessage(data_writer, msg)
        #disHelper.sendDiscordMsg(msg)
    
    # if balance > balanceThreshold + notifyThreshold, then notify via Discord
    if balance > 0.0: # 1.0:
        upperThreshold = (instrument.notifyBalanceThreshold + instrument.notifyBalanceThresholdDelta)
        if balance > upperThreshold :
            # find highest multiple of threshold delta below current balance, then add another delta
            instrument.notifyBalanceThreshold = ((balance // instrument.notifyBalanceThresholdDelta) * instrument.notifyBalanceThresholdDelta) + instrument.notifyBalanceThresholdDelta
            return True
            #instrument.balanceThreshold = (instrument.balanceThreshold + instrument.notifyBalanceThreshold)

        lowerThreshold = (instrument.notifyBalanceThreshold - instrument.notifyBalanceThresholdDelta)        
        if balance < lowerThreshold :
            # find highest multiple of threshold delta below current balance
            instrument.notifyBalanceThreshold = (balance // instrument.notifyBalanceThresholdDelta) * instrument.notifyBalanceThresholdDelta
            return True
            # msg = (f"@here {instrument.symbol} DOWN {instrument.notifyBalanceThreshold} to {round(instrument.balanceGBP['balance'],2)}, new threshold at {instrument.balanceThreshold}")
            # printLogMessage(data_writer, msg)
            # disHelper.sendDiscordMsg(msg)
    return False

def NotifyAboutPrice(writer, discordHelper, oldThreshold, instrument):
    movement = "DOWN"
    if instrument.coinPriceUSDT > oldThreshold:
        movement = "UP"
    msg = (f"@here {getTime()} {instrument.symbol} price {movement} from {oldThreshold} to {round(instrument.coinPriceUSDT,2)}, new threshold at {instrument.notifyPriceThreshold}")
    printLogMessage(writer, msg)
    discordHelper.sendDiscordMsg(msg)

def NotifyAboutBalance(writer, discordHelper, oldThreshold, instrument):
    movement = "DOWN"
    if instrument.balanceGBP['balance'] > oldThreshold:
        movement = "UP"
    msg = (f"@here {getTime()} {instrument.symbol} balance {movement} from {oldThreshold} to {round(instrument.balanceGBP['balance'],2)}, new threshold at {instrument.notifyBalanceThreshold}")
    printLogMessage(writer, msg)
    discordHelper.sendDiscordMsg(msg)

if __name__ == '__main__':
    priceBaseline           = 0
    displayLineLength       = 100           # for display only - the number of character spaces used to display price marker
    sleepDelayMin           = 5             # time between querying the binance API
    #notifyBalanceThreshold  = 20.0          # how far the profit value should move in GBP before notifying
    #balanceThreshold    = 0.0           # baseline profit value used to measure profit movement for notification purposes
    CheckPrice = False
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
    # define instruments to track, and a list of instruments required to convert to a base of USDT
    # final conversion of USDT to GBP will be done later.
    # the notifyPrice and notifyBalance threshold argumetns are in GBP
    account.instruments.append(Instrument("DOGE", ["DOGEUSDT"], 250, 250))
    account.instruments.append(Instrument("BTC", ["BTCUSDT"], 250, 250))
    account.instruments.append(Instrument("ETH", ["ETHBTC", "BTCUSDT"], 250, 250))

    balances = binHelper.getAccountBalances()

    #print(balances['balances'])
    printCoinBalances(balances)

   # allInstrumentNames = binHelper.getAllInstrumentNames()

    
    with open(f"cryptobot_log_{getDateStr()}.csv", 'w', newline ='') as csv_file :
        data_writer = csv.writer(csv_file, delimiter=',') 
        disHelper.sendDiscordMsg(f"New run starting at {getDateStr()}")   
        print("starting loop")
        while(True):
            
            for instr in account.instruments:
                #print(f"updating {instr.symbol}:")
                # get number of coins
                coin_total = binHelper.getAccountBalanceForSymbol(instr.symbol)
                if coin_total is None:
                    print("couldn't get balance")
                    continue
                #print(f"coin_total for {instr.symbol} = {coin_total}")
                instr.coinTotal = coin_total
                if instr.coinTotal == 0.0:
                    #print(f"skipping {instr.symbol} for zero balance")
                    continue
                # get the coin value in BTC (used as stepping stone to cal value in GBP)
                instr.coinPriceUSDT = getCoinPriceInUSDT(instr)

                GBPUSDT_price_obj = binHelper.getPrice("GBPUSDT")
                GBPUSDT_price = float(GBPUSDT_price_obj['bidPrice'])      # extract the bidPrice from the object
                instr.coinPriceGBP = instr.coinPriceUSDT / GBPUSDT_price

                #instrument.coinPriceUSDT = current_coin_price_USDT
                instr.balanceGBP['balance'] = instr.coinPriceGBP * instr.coinTotal
                instr.balanceGBP['max'] = max(instr.balanceGBP['balance'], instr.balanceGBP['max'])
                instr.balanceGBP['min'] = min(instr.balanceGBP['balance'], instr.balanceGBP['min'])
                # if instr.balanceGBP['balance'] > instr.balanceGBP['max']:
                #     instr.balanceGBP['max'] = instr.balanceGBP['balance']
                # if instr.balanceGBP['balance'] < instr.balanceGBP['min']:
                #     instr.balanceGBP['min'] = instr.balanceGBP['balance']

                instr.balanceUSDT['balance'] = instr.coinPriceUSDT * instr.coinTotal
                instr.balanceUSDT['max'] = max (instr.balanceUSDT['balance'], instr.balanceUSDT['max'])
                instr.balanceUSDT['min'] = min (instr.balanceUSDT['balance'], instr.balanceUSDT['min'])
                # if instr.balanceUSDT['balance'] > instr.balanceUSDT['max']:
                #     instr.balanceUSDT['max'] = instr.balanceUSDT['balance']
                # if instr.balanceUSDT['balance'] < instr.balanceUSDT['min']:
                #     instr.balanceUSDT['min'] = instr.balanceUSDT['balance']

                # print balances for coins if > 1.0GBP
                #if instr.balanceGBP['balance'] > 1.0:
                justCoinPriceGBP = str(round(Decimal(instr.coinPriceGBP),5))
                justCoinPriceUSDT = str(round(Decimal(instr.coinPriceUSDT),5))
                justCoinTotal = str(round(Decimal(instr.coinTotal),8))
                justCoinBalance = str(round(Decimal(instr.balanceGBP['balance']),2))
                
                printLogMessage(data_writer, f"{instr.symbol.rjust(4,' ')} Price £:{justCoinPriceGBP.rjust(15,' ')}, Price $:{justCoinPriceUSDT.rjust(15,' ')}, Total coins:{justCoinTotal.rjust(15,' ')}, Upper Thr: { instr.notifyBalanceThreshold + instr.notifyBalanceThresholdDelta}, Lower Thr: { instr.notifyBalanceThreshold - instr.notifyBalanceThresholdDelta}, Balance £:{justCoinBalance.rjust(10,' ')}")
                
                # set threshold from which to measure price movement.
                currentThreshold = instr.notifyPriceThreshold
                if(CheckNotifyAboutPrice(instr)):
                    NotifyAboutPrice(data_writer, disHelper, currentThreshold, instr)
                currentThreshold = instr.notifyBalanceThreshold
                if(CheckNotifyAboutBalance(instr)):
                    NotifyAboutBalance(data_writer, disHelper, currentThreshold, instr)

                



                #distanceToPriceThreshold = abs(instr.balanceGBP['balance'] - instr.balanceThreshold)
                ## print(f"distanceToPriceThreshold:{distanceToPriceThreshold:.4f}")
                #if distanceToPriceThreshold > instr.notifyPriceThreshold:
                #     discordMsg += (f"{instr.symbol} reached {notifyPriceThreshold}, now at {current_coin_price_USDT}")
                #     #disHelper.sendDiscordMsg(f"{account.symbol} reached {notifyPriceThreshold}, now at {current_coin_price_USDT}")
                #     notifyPriceThreshold = getNotifyPriceThreshold(current_coin_price_USDT)


                # print balance line
                msg = f"{getTime()}: {instr.symbol} : {instr.coinPriceUSDT:.4f} : {round(instr.balanceGBP['min'])} : {round(instr.balanceGBP['max'])} : {round(instr.balanceGBP['balance'])}"#round up == false
                data_writer.writerow([msg])

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
