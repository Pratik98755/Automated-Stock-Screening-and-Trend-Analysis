import mainv2
import datetime
from datetime import timedelta
import os

# Create NSE instance
nse = mainv2.NSEMasterData()

# Download NSE master data
nse.download_symbol_master()

# Search for a symbol (optional)
symbols_found = nse.search('NIFTY BANK', exchange='NSE', match=False)
print(symbols_found)

# Check NSE data loaded
print("NSE Master Data loaded:", len(nse.nse_data), "symbols")

os.makedirs("symbols_ohlcv", exist_ok=True)


# symbols = ['INFY', 'HDFCBANK', 'MINDACORP', 'VIMTALABS']
# symbols = ['SBIN', 'JIOFIN', 'TCS', 'WIPRO']
# symbols = ['RAMCOSYS','BLUESTONE','SBIN', 'JIOFIN', 'TCS', 'WIPRO','INFY', 'HDFCBANK', 'MINDACORP', 'VIMTALABS','ASTERDM' ,'NATIONALUM','ANANTRAJ','SYRMA','NELCO']
# Read symbols from file
with open("input_symbols.txt", "r") as f:
    symbols = [line.strip().upper() for line in f if line.strip()]


# Fetch 15-minute OHLCV data for past 4 days
for symbol in symbols:
    data = nse.get_history(
        symbol=symbol,                   
        exchange='NSE',
        start=datetime.datetime.now() - datetime.timedelta(days=10),
        end=datetime.datetime.now(),
        interval='15m'
    )

    if data is not None and not data.empty:
        out_path = f"./symbols_ohlcv/{symbol}_15m.csv"
        data.to_csv(out_path, index=True)
        print(f"✅ Saved to {out_path} ({len(data)} rows)")
    else:
        print(f"⚠️ No data returned for {symbol}")
