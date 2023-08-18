from dotenv import load_dotenv
import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoLatestQuoteRequest
import simplejson as json
import asyncio
import websocket

load_dotenv()

api_key = os.getenv("API_KEY_PAPER")
api_secret = os.getenv("API_SECRET_PAPER")
websocket_url = "wss://stream.data.alpaca.markets/v1beta3/crypto/us"
auth_msg = {"action": "auth", "key": api_key, "secret": api_secret}

client = CryptoHistoricalDataClient(api_key, api_secret)
multisymbol_request_params = CryptoLatestQuoteRequest(symbol_or_symbols=["BTC/USD", "ETH/BTC", "ETH/USD"])

waitTime = 3
minPercentDiff = 0.05
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
#buying_power = float(account.cash)
buying_power = 50000

async def updatePrices():
    latest = client.get_crypto_latest_quote(multisymbol_request_params, feed= "us")
    for symbol in latest:
        prices[symbol + "-A"] = latest[symbol].ask_price
        prices[symbol + "-B"] = latest[symbol].bid_price

def make_order(symbol, qty, side):
    market_order_data = MarketOrderRequest(
                            symbol=symbol,
                            qty=qty,
                            side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                            time_in_force=TimeInForce.GTC
                        )
    try: 
        market_order = trading_client.submit_order(market_order_data)
        if market_order:
            return True
        else:
            return False
    except Exception as e:
        print(e)
        return False
    
'''
USD / ETHa * ETHBTCa * BTCb
USD / BTCa / ETHBTCb * ETHb
'''
    
async def arbitrage(prices):
    global buying_power
    buy_eth = buying_power / prices["ETH/USD-A"]
    buy_btc = buying_power / prices["BTC/USD-A"]
    sell_btc = buy_eth * prices["ETH/BTC-B"]
    buy_ethwbtc = buy_btc / prices["ETH/BTC-A"]
    profit1 = 1.0 / prices["ETH/USD-A"] * prices["ETH/BTC-A"] * prices["BTC/USD-B"]
    profit2 = 1.0 / prices["BTC/USD-A"] / prices["ETH/BTC-B"] * prices["ETH/USD-B"]

    if (profit1 > (1.0 + minPercentDiff/100)):
        if make_order("ETH/USD", buy_eth, "buy"):
            if make_order("ETH/BTC", buy_eth, "sell"):
                if make_order("BTC/USD", sell_btc, "sell"):
                    print("Arbitrage Completed")
                else:
                    make_order("ETH/BTC", buy_eth, "buy")
                    make_order("ETH/USD", buy_eth, "sell")
                    exit()
            else:
                make_order("ETH/USD", buy_eth, "sell")
                exit()
        else:
            exit()
    elif (profit2 > (1.0 + minPercentDiff/100)):
        if make_order("BTC/USD", buy_btc, "buy"):
            if make_order("ETH/BTC", buy_ethwbtc, "buy"):
                if make_order("ETH/USD", buy_ethwbtc, "sell"):
                    print("Arbitrage Completed")
                else:
                    make_order("ETH/BTC", buy_ethwbtc,"sell")
                    make_order("BTC/USD", buy_btc,"sell")
                    exit()
            else:
                make_order("BTC/USD", buy_btc, "sell")
                exit()
        else:
            exit()
    else:
        print("No Arbitrage. {} {}".format(profit1, profit2))
    #buying_power = float(account.cash)

async def main():
    while True:
        await updatePrices()
        await arbitrage(prices)
        await asyncio.sleep(waitTime)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.close()


