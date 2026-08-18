import pandas as pd
import requests
import time
import re

from datetime import datetime, timedelta


class NSEMasterData:

    def __init__(self):

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/138.0 Safari/537.36",

            "Accept": "application/json",
            "Referer": "https://www.nseindia.com/",
            "Origin": "https://www.nseindia.com"
        })

        # New NSE endpoints
        self.symbol_url = (
            "https://charting.nseindia.com/v1/exchanges/symbolsDynamic"
        )

        self.history_url = (
            "https://charting.nseindia.com/v1/charts/symbolHistoricalData"
        )

        self.nse_data = pd.DataFrame()
        self.nfo_data = pd.DataFrame()

        # Warm session
        try:
            self.session.get(
                "https://www.nseindia.com",
                timeout=10
            )
        except:
            pass



    def download_symbol_master(self):
        """
        Dummy download function.

        The new NSE API doesn't expose a downloadable master file anymore.
        We keep this function so old code continues to work.
        """
        self.nse_data = pd.DataFrame()
        self.nfo_data = pd.DataFrame()


    def search(self, symbol, exchange="NSE", match=False):

        params = {
            "symbol": symbol,
            "segment": ""
        }

        try:

            r = self.session.get(
                self.symbol_url,
                params=params,
                timeout=15
            )

            r.raise_for_status()

            js = r.json()

            if not js.get("status"):
                return pd.DataFrame()

            rows = []

            for item in js["data"]:

                typ = item.get("type", "")

                # Exchange filter
                if exchange.upper() == "NSE":
                    if item["exchange"] != "NSE":
                        continue
                    if typ != "Equity":
                        continue

                elif exchange.upper() == "NFO":
                    if typ == "Equity":
                        continue

                rows.append({

                    "ScripCode": item["scripcode"],
                    "Symbol": item["symbol"],
                    "Name": item["description"],
                    "Type": typ

                })

            df = pd.DataFrame(rows)

            if match and not df.empty:
                df = df[df["Symbol"].str.upper() == symbol.upper()]

            return df.reset_index(drop=True)

        except Exception as e:

            print(e)
            return pd.DataFrame()


    def search_symbol(self, symbol, exchange):

        df = self.search(symbol, exchange, match=False)

        if df.empty:
            return None

        return df.iloc[0]
    




    def get_history(self,
                    symbol="NIFTY",
                    exchange="NSE",
                    start=None,
                    end=None,
                    interval="1d"):

        symbol_info = self.search_symbol(symbol, exchange)

        if symbol_info is None:
            return pd.DataFrame()

        interval_map = {
            "1m": ("1", "I"),
            "3m": ("3", "I"),
            "5m": ("5", "I"),
            "10m": ("5", "I"),      # aggregate later
            "15m": ("15", "I"),
            "30m": ("30", "I"),
            "1h": ("60", "I"),
            "1d": ("1", "D"),
            "1w": ("1", "W"),
            "1M": ("1", "M")
        }

        api_interval, chart_type = interval_map[interval]

        params = {

            "token": symbol_info["ScripCode"],

            "symbol": symbol_info["Symbol"],

            "symbolType": symbol_info["Type"],

            "fromDate":
                int(start.timestamp()) if start else 0,

            "toDate":
                int(end.timestamp()) if end else int(time.time()),

            "chartType": chart_type,

            "timeInterval": api_interval

        }

        try:

            r = self.session.get(
                self.history_url,
                params=params,
                timeout=20
            )

            r.raise_for_status()

            js = r.json()

            print("start =", start)
            print("end   =", end)
            print("from =", int(start.timestamp()))
            print("to   =", int(end.timestamp()))

            if not js["status"]:
                return pd.DataFrame()

            rows = []

            for candle in js["data"]:

                rows.append({

                    "Timestamp":
                        pd.to_datetime(candle["time"], unit="ms"),

                    "Open":
                        candle["open"],

                    "High":
                        candle["high"],

                    "Low":
                        candle["low"],

                    "Close":
                        candle["close"],

                    "Volume":
                        candle["volume"]

                })

            df = pd.DataFrame(rows)

            if df.empty:
                return df

            df = df.sort_values("Timestamp")

            df.set_index("Timestamp", inplace=True)

            # Market close filter
            if chart_type == "I":

                df = df[
                    df.index.time <= pd.Timestamp("15:30").time()
                ]

            # -------- Aggregate 10-minute --------

            if interval == "10m":

                df = df.resample("10min").agg({

                    "Open": "first",

                    "High": "max",

                    "Low": "min",

                    "Close": "last",

                    "Volume": "sum"

                }).dropna()

            # -------- Aggregate 30-minute --------

            elif interval == "30m":

                df = df.resample("30min").agg({

                    "Open": "first",

                    "High": "max",

                    "Low": "min",

                    "Close": "last",

                    "Volume": "sum"

                }).dropna()

            # -------- Aggregate Hourly --------

            elif interval == "1h":

                df = df.resample("60min").agg({

                    "Open": "first",

                    "High": "max",

                    "Low": "min",

                    "Close": "last",

                    "Volume": "sum"

                }).dropna()

            return df

        except Exception as e:

            print("History Error:", e)

            return pd.DataFrame()
        





if __name__ == "__main__":

    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)

    nse = NSEMasterData()

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    # ---------------- SYMBOL SEARCH ----------------

    print("\n========== NSE SEARCH ==========")
    print(nse.search("SBIN", exchange="NSE"))

    print("\n========== NFO SEARCH ==========")
    print(nse.search("INFY", exchange="NFO").head())

    # ---------------- DAILY ----------------

    data = nse.get_history(
        symbol="SBIN",
        exchange="NSE",
        start=start_date,
        end=end_date,
        interval="1d"
    )

    print("\n========== SBIN DAILY ==========")
    print(data.head())

    # ---------------- 1 MIN ----------------

    data = nse.get_history(
        symbol="SBIN",
        exchange="NSE",
        start=start_date,
        end=end_date,
        interval="1m"
    )

    print("\n========== SBIN 1 MIN ==========")
    print(data.head())

    # ---------------- 5 MIN ----------------

    data = nse.get_history(
        symbol="SBIN",
        exchange="NSE",
        start=start_date,
        end=end_date,
        interval="5m"
    )

    print("\n========== SBIN 5 MIN ==========")
    print(data.head())

    # ---------------- 15 MIN ----------------

    data = nse.get_history(
        symbol="SBIN",
        exchange="NSE",
        start=start_date,
        end=end_date,
        interval="15m"
    )

    print("\n========== SBIN 15 MIN ==========")
    print(data.head())

    # ---------------- 30 MIN ----------------

    data = nse.get_history(
        symbol="SBIN",
        exchange="NSE",
        start=start_date,
        end=end_date,
        interval="30m"
    )

    print("\n========== SBIN 30 MIN ==========")
    print(data.head())

    # ---------------- 1 HOUR ----------------

    data = nse.get_history(
        symbol="SBIN",
        exchange="NSE",
        start=start_date,
        end=end_date,
        interval="1h"
    )

    print("\n========== SBIN 1 HOUR ==========")
    print(data.head())