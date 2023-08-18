from dotenv import load_dotenv
import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.live import CryptoDataStream
import simplejson as json
import asyncio

load_dotenv()

api_key = os.getenv("API_KEY_PAPER")
api_secret = os.getenv("API_SECRET_PAPER")
crypto_stream = CryptoDataStream(api_key, api_secret, raw_data=False, feed="us")

waitTime = 3
minPercentDiff = 0.5
ready = False

prices = {"ETH/USD-A": 0,
          "ETH/USD-B": 0, 
          "BTC/USD-A": 0,
          "BTC/USD-B": 0,
          "ETH/BTC-A": 0,
          "ETH/BTC-B": 0
        }

trading_client = TradingClient(api_key, api_secret, paper=True)
account = trading_client.get_account()
buying_power = 0.75 * float(account.cash)

async def quote_handler(data):
    global ready
    await updatePrices(data)
    if not ready:
        temp = True
        for i in prices:
            if prices[i] == 0:
                temp = False
        ready = temp        
    if ready:
        await arbitrage(prices)

async def updatePrices(data):
    symbol = data.symbol
    prices[symbol + "-A"] = data.ask_price
    prices[symbol + "-B"] = data.bid_price

async def make_order(sym, quantity, side):
    market_order_data = MarketOrderRequest(
                            symbol=sym,
                            qty=quantity,
                            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                            time_in_force=TimeInForce.GTC
                        )
        
    try: 
        market_order = trading_client.submit_order(market_order_data)
        for symbol, value in market_order:
            print("{}: {}".format(symbol, value))
        return market_order
    except Exception as e:
        print(e)
        return False
    
async def make_order_notional(sym, notionalamt, side):
    market_order_data = MarketOrderRequest(
                            symbol=sym,
                            notional=notionalamt,
                            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                            time_in_force=TimeInForce.GTC
                        )
        
    try: 
        market_order = trading_client.submit_order(market_order_data)
        for symbol, value in market_order:
            print("{}: {}".format(symbol, value))
        return market_order
    except Exception as e:
        print(e)
        return False
    
'''
USD / ETHa * ETHBTCb * BTCb
USD / BTCa / ETHBTCa * ETHb
'''
    
async def arbitrage(prices):
    global buying_power
    buy_eth = buying_power / prices["ETH/USD-A"]
    buy_btc = buying_power / prices["BTC/USD-A"]
    profit1 = 1.0 / prices["ETH/USD-B"] * prices["ETH/BTC-A"] * prices["BTC/USD-A"]
    profit2 = 1.0 / prices["BTC/USD-B"] / prices["ETH/BTC-B"] * prices["ETH/USD-A"]

    if (profit1 > (1.0 + minPercentDiff/100)):
        order1 = await make_order("ETH/USD", buy_eth, "buy")
        if order1:
            qty1 = trading_client.get_open_position("ETH/USD").qty
            order2 = await make_order("ETH/BTC", qty1, "sell")
            if order2:
                qty2 = trading_client.get_open_position("BTC/USD").qty
                order3 = await make_order("BTC/USD", qty2, "sell")
                if order3:
                    print("Arbitrage Completed")
                else:
                    print("order3 fail (1)")
                    trading_client.close_all_positions(cancel_orders=False)
                    exit()
            else:
                print("order2 fail (1)")
                trading_client.close_all_positions(False)
                exit()
        else:
            print("order1 fail (1)")
            exit()
    elif (profit2 > (1.0 + minPercentDiff/100)):
        order1 = await make_order("BTC/USD", buy_btc, "buy")
        if order1:
            qty1 = trading_client.get_open_position("BTC/USD").qty
            order2 = await make_order_notional("ETH/BTC", qty1, "buy")
            if order2:
                qty2 = trading_client.get_open_position("ETH/USD").qty
                order3 = await make_order("ETH/USD", qty2, "sell")
                if order3:
                    print("Arbitrage Completed")
                else:
                    print("order3 fail (2)")
                    trading_client.close_all_positions(False)
                    exit()
            else:
                print("order2 fail (2)")
                trading_client.close_all_positions(False)
                exit()
        else:
            print("order1 fail (2)")
            exit()
    else:
        print("No Arbitrage. {} {}".format(profit1, profit2))
    #buying_power = 0.75 * float(account.cash)

def main():
    crypto_stream.subscribe_quotes(quote_handler, "BTC/USD", "ETH/USD", "ETH/BTC")
    crypto_stream.run()

if __name__ == "__main__":
    main()


