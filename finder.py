




#!/usr/bin/env python3
"""
find_bounce_supports.py (Fixed version for index-based trendlines)

Scans symbols_ohlcv/*.csv and trendline_logs/*_15m_trendline_log.csv,
finds symbols likely to bounce from support trendlines, and optionally saves continuous plots.

FIXED: Uses index-based trendline coordinates to match the trendline generation script.
"""

import os
import glob
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


# ----------------------- ARGS -----------------------
def parse_args():
    p = argparse.ArgumentParser(description="Find symbols likely to bounce from support trendline.")
    p.add_argument('--symbol_folder', '-s', default='symbols_ohlcv', help='Folder with {SYMBOL}_15m.csv files')
    p.add_argument('--trend_folder', '-t', default='trendline_logs', help='Folder with {SYMBOL}_15m_trendline_log.csv files')
    p.add_argument('--close_pct', type=float, default=0.5, help='Close percentage threshold (e.g. 2 for 2%)')
    p.add_argument('--candles_up', type=int, default=7, help='Number of recent candles that must be above the trendline')
    p.add_argument('--save_plots', action='store_true', help='Save PNG plots for passing symbols')
    p.add_argument('--verbose', '-v', action='store_true', help='Verbose debug prints')
    return p.parse_args()


# ----------------------- READERS -----------------------
def read_ohlcv(filepath):
    df = pd.read_csv(filepath, parse_dates=['Timestamp'])
    df = df.sort_values('Timestamp').reset_index(drop=True)
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def read_trendlog(filepath):
    df = pd.read_csv(filepath, dtype=str)
    if 'type' not in df.columns:
        return pd.DataFrame()

    # Convert numeric columns
    for col in ['y1_price', 'y2_price', 'slope', 'intercept', 'extended']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df


# ----------------------- INDEX-BASED SUPPORT PRICE -----------------------
def trend_price_at_index(slope, intercept, index):
    """Calculate trendline price at specific index using slope-intercept form"""
    return slope * index + intercept


def find_trendline_indices(df, x1_time, x2_time):
    """Convert timestamps to dataframe indices"""
    # Find the closest indices for the trendline points
    x1_idx = df.index[df['Timestamp'] >= x1_time][0] if len(df[df['Timestamp'] >= x1_time]) > 0 else 0
    x2_idx = df.index[df['Timestamp'] >= x2_time][0] if len(df[df['Timestamp'] >= x2_time]) > 0 else len(df)-1
    return x1_idx, x2_idx


# ----------------------- EVALUATION -----------------------
def evaluate_symbol(symbol, df, tdf, close_pct, candles_up, verbose=False):
    supports = tdf[tdf['type'].str.lower() == 'support'].copy()
    if supports.empty:
        if verbose:
            print(f"[{symbol}] No support trendlines.")
        return None, None

    # Use last 100 candles for evaluation (matching plot)
    df_eval = df.tail(100).reset_index(drop=True)
    latest_idx = len(df_eval) - 1

    # Compute price at latest candle for each support line using INDEX-BASED calculation
    supports['price_latest'] = supports.apply(
        lambda r: trend_price_at_index(r['slope'], r['intercept'], latest_idx),
        axis=1
    )
    supports = supports.dropna(subset=['price_latest'])
    if supports.empty:
        return None, None

    # Choose the highest support (closest to current price)
    chosen = supports.loc[supports['price_latest'].idxmax()]

    # Perform checks using INDEX-BASED calculations
    slope, intercept = chosen['slope'], chosen['intercept']
    latest = df_eval.iloc[-1]
    open_latest, close_latest, low_latest = latest['Open'], latest['Close'], latest['Low']
    p_latest = trend_price_at_index(slope, intercept, latest_idx)

    # Check 1: Candle body above support (Open AND Close above support)
    if not (open_latest > p_latest and close_latest > p_latest):
        if verbose:
            print(f"[{symbol}] Body not above support. Open={open_latest:.2f}, Close={close_latest:.2f}, Support={p_latest:.2f}")
        return None, supports

    # Check 2: Close within close_pct of support
    upper_allowed = p_latest * (1 + close_pct / 100.0)
    if not (p_latest <= close_latest <= upper_allowed):
        if verbose:
            print(f"[{symbol}] Close {close_latest:.2f} not within {close_pct}% of {p_latest:.2f}")
        return None, supports

    # Check 3: Last N candles above support
    recent = df_eval.iloc[-candles_up:].copy()
    for i, (idx, row) in enumerate(recent.iterrows()):
        pt = trend_price_at_index(slope, intercept, idx)
        if not (row['Open'] > pt and row['Close'] > pt):
            if verbose:
                print(f"[{symbol}] Candle {i+1} periods back below support.")
            return None, supports

    if verbose:
        print(f"[{symbol}] ✅ PASSED. Support@{p_latest:.2f}, Close={close_latest:.2f}")

    # DEBUG output
    if verbose:
        print(f"\n[{symbol}] DEBUG:")
        print(f"  Trendline: slope={slope:.4f}, intercept={intercept:.2f}")
        print(f"  Latest index: {latest_idx}, Support price: {p_latest:.2f}")
        print(f"  Candle: O={open_latest:.1f} H={latest['High']:.1f} L={low_latest:.1f} C={close_latest:.1f}")
        print(f"  Low above support: {low_latest:.1f} > {p_latest:.2f} = {low_latest > p_latest}")

    return chosen, supports


# ----------------------- CONTINUOUS PLOT -----------------------
def plot_symbol(symbol, df, supports, chosen, save_dir):
    os.makedirs(save_dir, exist_ok=True)
    plt.figure(figsize=(12, 6))

    # --- Use last 100 candles only ---
    df_plot = df.tail(100).reset_index(drop=True)
    latest_idx = len(df_plot) - 1

    # Plot continuous candles using index
    for i in range(len(df_plot)):
        r = df_plot.iloc[i]
        color = 'green' if r['Close'] >= r['Open'] else 'red'
        plt.plot([i, i], [r['Low'], r['High']], color=color, linewidth=1)
        plt.plot([i, i], [r['Open'], r['Close']], color=color, linewidth=4)

    # Plot all support lines using INDEX-BASED coordinates
    for _, s in supports.iterrows():
        slope, intercept = s['slope'], s['intercept']
        extended = s.get('extended', 0)
        
        # Calculate start and end indices for plotting
        if pd.notna(s.get('x1_time')) and pd.notna(s.get('x2_time')):
            x1_idx, x2_idx = find_trendline_indices(df_plot, s['x1_time'], s['x2_time'])
        else:
            # Fallback: use reasonable range
            x1_idx = 0
            x2_idx = latest_idx
        
        # Extend the trendline
        end_idx = min(latest_idx + extended, latest_idx + 20)  # Max extension
        
        # Plot the trendline
        xs = [x1_idx, end_idx]
        ys = [slope * x + intercept for x in xs]
        plt.plot(xs, ys, color='gray', linestyle='--', linewidth=1, alpha=0.7)

    # Highlight chosen support line
    if chosen is not None:
        slope, intercept = chosen['slope'], chosen['intercept']
        extended = chosen.get('extended', 0)
        
        if pd.notna(chosen.get('x1_time')) and pd.notna(chosen.get('x2_time')):
            x1_idx, x2_idx = find_trendline_indices(df_plot, chosen['x1_time'], chosen['x2_time'])
        else:
            x1_idx = 0
            x2_idx = latest_idx
        
        # Extend chosen trendline
        end_idx = min(latest_idx + extended, latest_idx + 20)
        
        xs = [x1_idx, end_idx]
        ys = [slope * x + intercept for x in xs]
        plt.plot(xs, ys, color='lime', linewidth=2.5, label='Chosen Support')
        
        # Mark the support price at latest candle
        support_price = slope * latest_idx + intercept
        plt.axhline(y=support_price, color='lime', linestyle=':', alpha=0.7, label=f'Support: {support_price:.2f}')

    # Add price markers for latest candle
    latest = df_plot.iloc[-1]
    plt.axhline(y=latest['Close'], color='blue', linestyle='--', alpha=0.5, label=f'Close: {latest["Close"]:.2f}')

    plt.title(f"{symbol} | Support Bounce Analysis (last 100 candles)")
    plt.xlabel("Candle Index")
    plt.ylabel("Price")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()

    outpath = os.path.join(save_dir, f"{symbol}_support.png")
    plt.savefig(outpath, dpi=150, bbox_inches='tight')
    plt.close()


# ----------------------- MAIN -----------------------
def main():
    args = parse_args()
    files = sorted(glob.glob(os.path.join(args.symbol_folder, '*_15m.csv')))
    if not files:
        print("❌ No symbol files found in", args.symbol_folder)
        return

    passing = []
    for f in files:
        symbol = os.path.basename(f).replace('_15m.csv', '')
        trendfile = os.path.join(args.trend_folder, f"{symbol}_15m_trendline_log.csv")
        if not os.path.exists(trendfile):
            continue

        try:
            df = read_ohlcv(f)
            tdf = read_trendlog(trendfile)
            chosen, supports = evaluate_symbol(symbol, df, tdf, args.close_pct, args.candles_up, verbose=args.verbose)
            if chosen is not None:
                passing.append(symbol)
                if args.save_plots:
                    plot_symbol(symbol, df, supports, chosen, "support_plots")
        except Exception as e:
            if args.verbose:
                print(f"[{symbol}] ERROR: {e}")

    if passing:
        print("\n✅ Symbols likely to bounce up from support:")
        for s in passing:
            print(" -", s)
    else:
        print("\nNo symbols passed the criteria.")


if __name__ == "__main__":
    main()