
# =============================================================
# FOR INDIAN MARKET TIMING (9:15AM TO 3:30PM) RUNNING STOCKS
# =============================================================

#!/usr/bin/env python3
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import timedelta

# Ensure UTF-8 prints (optional)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# --------- CONFIG ----------
INPUT_DIR = "symbols_ohlcv"
OUTPUT_DIR = "trendlined_symbols"
LOG_DIR = "trendline_logs"

WINDOW_SIZE = 100
PRICE_BUFFER_PCT = 0.3        # how close a swing point must be to the line (percentage)
MIN_GAP = 4                   # minimum gap (in candles) between swing points
TRENDLINE_EXTENSION = 20      # how many candles to extend the latest trendlines by
BB_CHECK_STEPS = 3
BB_MAX_INTERSECTIONS = 1
BB_MAX_PENETRATION_PCT = 0.3  # price percentage allowed when testing intersections
VALID_TOUCHES_MIN = 3

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ----------------- helpers -----------------
def calculate_bollinger_bands(df, length=20, mult=2.0):
    basis = df["close"].rolling(window=length, min_periods=1).mean()
    stdev = df["close"].rolling(window=length, min_periods=1).std(ddof=0)
    upper = basis + mult * stdev
    lower = basis - mult * stdev
    return upper, lower

def extend_time(ts, minutes_per_candle=5, steps=30):
    return ts + timedelta(minutes=minutes_per_candle * steps)

def find_swing_points(df, window=2, min_gap=3, tolerance=0.0):
    swing_lows, swing_highs = [], []
    last_low_idx, last_high_idx = -min_gap - 1, -min_gap - 1
    L = len(df)
    for i in range(window, L - window):
        local_lows = df["low"].iloc[i - window:i + window + 1]
        local_highs = df["high"].iloc[i - window:i + window + 1]
        current_low = df["low"].iloc[i]
        current_high = df["high"].iloc[i]
        if abs(current_low - local_lows.min()) <= tolerance and (i - last_low_idx) > min_gap:
            swing_lows.append(i)
            last_low_idx = i
        if abs(current_high - local_highs.max()) <= tolerance and (i - last_high_idx) > min_gap:
            swing_highs.append(i)
            last_high_idx = i
    return swing_lows, swing_highs

def log_trendline(logs, line_type, idx1, idx2, slope, intercept, df, extended=0):
    t1 = df["open_time"].iloc[idx1]
    t2 = df["open_time"].iloc[idx2]
    price_col = "low" if ("low" in line_type.lower() or "support" in line_type.lower()) else "high"
    p1 = float(df[price_col].iloc[idx1])
    p2 = float(df[price_col].iloc[idx2])
    norm_type = "support" if ("low" in line_type.lower() or "support" in line_type.lower()) else \
                ("resistance" if ("high" in line_type.lower() or "resistance" in line_type.lower()) else line_type.lower())
    logs.append({
        "type": norm_type,
        "x1_time": pd.Timestamp(t1).isoformat(),
        "x2_time": pd.Timestamp(t2).isoformat(),
        "y1_price": p1,
        "y2_price": p2,
        "slope": slope,
        "intercept": intercept,
        "extended": int(extended)
    })

# def find_valid_trendlines(df, swing_indices, mode='low', price_buffer_pct=0.3, max_intersections=1, max_penetration_pct=0.3):
#     valid_lines = []
#     n = len(swing_indices)
#     if n < 2:
#         return valid_lines

#     for i in range(n - 1):
#         for j in range(i + 1, n):
#             idx1, idx2 = swing_indices[i], swing_indices[j]
#             x1 = idx1  # Use index position
#             y1 = df[mode].iloc[idx1]
#             x2 = idx2  # Use index position
#             y2 = df[mode].iloc[idx2]
#             if x1 == x2:
#                 continue
#             slope = (y2 - y1) / (x2 - x1)
#             intercept = y1 - slope * x1

#             # how many swing points (other than the pair) are within price_buffer_pct
#             touches = 2
#             for k in range(n):
#                 if k == i or k == j:
#                     continue
#                 idxk = swing_indices[k]
#                 xk = idxk  # Use index position
#                 yk = df[mode].iloc[idxk]
#                 y_on_line = slope * xk + intercept
#                 price_diff = abs(yk - y_on_line)
#                 if price_diff <= yk * (price_buffer_pct / 100):  # Percentage-based
#                     touches += 1


def find_valid_trendlines(df, swing_indices, mode='low', price_buffer_pct=0.3, max_intersections=1, max_penetration_pct=0.3):
    valid_lines = []
    n = len(swing_indices)
    if n < 2:
        return valid_lines

    for i in range(n - 1):
        for j in range(i + 1, n):
            idx1, idx2 = swing_indices[i], swing_indices[j]
            x1 = idx1
            y1 = df[mode].iloc[idx1]
            x2 = idx2
            y2 = df[mode].iloc[idx2]
            if x1 == x2:
                continue
            slope = (y2 - y1) / (x2 - x1)
            intercept = y1 - slope * x1

            # COUNT ONLY SWING POINTS FROM THE SAME SET (no mixing!)
            touches = 2  # The 2 defining points
            
            # Check all other swing points in the same set
            for k in range(n):
                if k == i or k == j:
                    continue
                idxk = swing_indices[k]
                # Only count if this swing point is between the two endpoints
                if idx1 < idxk < idx2 or idx2 < idxk < idx1:
                    xk = idxk
                    yk = df[mode].iloc[idxk]
                    y_on_line = slope * xk + intercept
                    price_diff = abs(yk - y_on_line)
                    if price_diff <= yk * (price_buffer_pct / 100):
                        touches += 1


            

            # intersections: check body midpoints across visible df
            intersections = 0
            total_penetration = 0.0
            for m in range(len(df)):
                x_m = m  # Use index position
                y_m = slope * x_m + intercept
                open_price = df["open"].iloc[m]
                close_price = df["close"].iloc[m]
                body_mid = (open_price + close_price) / 2
                penetration = abs(y_m - body_mid)
                if penetration <= body_mid * (max_penetration_pct / 100):  # Percentage-based
                    intersections += 1
                    total_penetration += penetration

            if touches >= VALID_TOUCHES_MIN and intersections <= max_intersections:
                valid_lines.append(((idx1, idx2), slope, intercept, touches))

    return valid_lines

def filter_trendline_by_bollinger(line, df, after_idx, steps=3):
    _, slope, intercept, _ = line
    max_idx = min(after_idx + steps, len(df) - 1)
    for i in range(after_idx + 1, max_idx + 1):
        x = i  # Use index position
        y = slope * x + intercept
        if pd.isna(df["bb_lower"].iloc[i]) or pd.isna(df["bb_upper"].iloc[i]):
            return False
        if y < df["bb_lower"].iloc[i] or y > df["bb_upper"].iloc[i]:
            return False
    return True

def draw_bb_filtered_lines(ax, df, swing_indices, mode, color, last_idx, logs, candle_interval_minutes, steps=3, max_intersections=1, max_penetration_pct=0.3, extension=20):
    if not swing_indices or last_idx < 0 or last_idx >= len(df):
        return

    best_line = None
    best_score = float('inf')

    # Step 1: try BB-filtered lines (from previous swing -> last_idx)
    for i in range(len(swing_indices) - 1):
        idx1 = swing_indices[i]
        idx2 = last_idx
        if idx1 >= idx2:
            continue
        x1 = idx1  # Use index position
        y1 = df[mode].iloc[idx1]
        x2 = idx2  # Use index position
        y2 = df[mode].iloc[idx2]
        if x1 == x2:
            continue
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - slope * x1
        virtual_line = ((idx1, idx2), slope, intercept, 0)

        if not filter_trendline_by_bollinger(virtual_line, df, last_idx, steps):
            continue

        intersections, total_penetration = 0, 0.0
        for j in range(last_idx + 1, min(last_idx + steps + 1, len(df))):
            t = j  # Use index position
            y_line = slope * t + intercept
            body_mid = (df["open"].iloc[j] + df["close"].iloc[j]) / 2
            penetration = abs(y_line - body_mid)
            if penetration <= body_mid * (max_penetration_pct / 100):  # Percentage-based
                intersections += 1
                total_penetration += penetration

        if intersections > max_intersections:
            continue

        avg_penetration = (total_penetration / intersections) if intersections > 0 else float('inf')
        if avg_penetration < best_score:
            best_score = avg_penetration
            best_line = ((idx1, idx2), slope, intercept)

    # Step 2: plot BB-best line if found
    if best_line:
        (idx1, idx2), slope, intercept = best_line
        x1dt = idx1
        x2dt = idx2 + extension  # Extend by index count
        xs = [x1dt, x2dt]
        ys = [slope * x + intercept for x in xs]
        ax.plot(xs, ys, linestyle='-', linewidth=2.5, color=color, label=f'BB Best {mode.capitalize()}')
        log_trendline(logs, f'BB Best {mode.capitalize()}', idx1, idx2, slope, intercept, df, extended=extension)
        return

    # Step 3: fallback validated line(s)
    fallback_candidates = [idx for idx in swing_indices if idx != last_idx]
    if not fallback_candidates:
        return

    def get_extreme(candidates):
        return min(candidates, key=lambda i: df["low"].iloc[i]) if mode == 'low' \
            else max(candidates, key=lambda i: df["high"].iloc[i])

    def validate_fallback(extreme_idx):
        x1 = extreme_idx  # Use index position
        y1 = df[mode].iloc[extreme_idx]
        x2 = last_idx  # Use index position
        y2 = df[mode].iloc[last_idx]
        if x1 == x2:
            return None
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - slope * x1
        intersections, total_penetration = 0, 0.0
        for j in range(last_idx + 1, min(last_idx + steps + 1, len(df))):
            t = j  # Use index position
            y_line = slope * t + intercept
            body_mid = (df["open"].iloc[j] + df["close"].iloc[j]) / 2
            penetration = abs(y_line - body_mid)
            if penetration <= body_mid * (max_penetration_pct / 100):  # Percentage-based
                intersections += 1
                total_penetration += penetration
        if intersections <= max_intersections:
            return slope, intercept, extreme_idx
        return None

    extreme_idx = get_extreme(fallback_candidates)
    result = validate_fallback(extreme_idx)
    if result is None and len(fallback_candidates) > 1:
        filtered = [i for i in fallback_candidates if i != extreme_idx]
        second_extreme_idx = get_extreme(filtered)
        result = validate_fallback(second_extreme_idx)
        if result:
            extreme_idx = second_extreme_idx

    if result:
        slope, intercept, extreme_idx = result
        x1dt = extreme_idx
        x2dt = last_idx + extension
        xs = [x1dt, x2dt]
        ys = [slope * x + intercept for x in xs]
        ax.plot(xs, ys, linestyle=':', linewidth=2, color=color, label=f'{mode.capitalize()} Fallback')
        log_trendline(logs, f'{mode.capitalize()} Fallback', extreme_idx, last_idx, slope, intercept, df, extended=extension)

def find_strict_trendline_from_latest_swing(
    ax,
    df,
    swing_indices,
    mode,
    last_idx,
    color,
    label_name,
    logs,
    candle_interval_minutes,
    extend_candles=20,
    price_buffer_pct=0.3      # Now using global percentage
):
    """
    Finds a strict trendline that:
    - Touches at least 3 swing points
    - Keeps all candle bodies on one side (strict)
    - Extends line into future by extend_candles
    """
    if not swing_indices or last_idx < 0 or last_idx >= len(df):
        return

    x2 = last_idx
    y2 = df[mode].iloc[last_idx]
    best_line = None
    best_touches = 0

    # Try connecting the latest swing to every earlier swing
    for idx1 in swing_indices:
        if idx1 >= last_idx:
            continue

        x1 = idx1
        y1 = df[mode].iloc[idx1]

        # Require directional validity
        if mode == "high" and y1 <= y2:
            continue
        if mode == "low" and y1 >= y2:
            continue

        # Line equation
        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - slope * x1

        # --- Count swing touches ---
        touches = 0
        for s_idx in swing_indices:
            y_line = slope * s_idx + intercept
            price_diff = abs(df[mode].iloc[s_idx] - y_line)
            if price_diff <= df[mode].iloc[s_idx] * (price_buffer_pct / 100):  # Using global percentage
                touches += 1

        # Must touch ≥ 3 swing points
        if touches < 3:
            continue

        # --- Validate all candle bodies are on correct side ---
        valid = True
        for mid_idx in range(x1, x2 + 1):
            if mid_idx >= len(df):
                break
            open_p = df["open"].iloc[mid_idx]
            close_p = df["close"].iloc[mid_idx]
            body_mid = (open_p + close_p) / 2
            y_line = slope * mid_idx + intercept

            if mode == "high" and body_mid > y_line + (body_mid * (price_buffer_pct / 100)):
                valid = False
                break
            if mode == "low" and body_mid < y_line - (body_mid * (price_buffer_pct / 100)):
                valid = False
                break

        if valid and touches > best_touches:
            best_touches = touches
            best_line = (x1, y1, slope, intercept)

    # --- Draw the best line ---
    if best_line:
        x1, y1, slope, intercept = best_line
        x2dt = last_idx
        x2dt_ext = last_idx + extend_candles
        xs = [x1, x2dt_ext]
        ys = [slope * x + intercept for x in xs]

        ax.plot(xs, ys, linestyle='-', linewidth=2.8, color=color, label=label_name)
        log_trendline(logs, label_name, x1, last_idx, slope, intercept, df, extended=extend_candles)
        print(f"[🧭] Strict trendline found ({label_name}): {best_touches} swing touches from {x1} → {last_idx}")

# =============================================================
# FOR INDIAN MARKET TIMING (9:15AM TO 3:30PM) RUNNING STOCKS
# =============================================================

def analyze_symbol(csv_path):
    base_name = os.path.basename(csv_path).rsplit(".", 1)[0]
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[ERROR] Cannot read {csv_path}: {e}")
        return

    # Standardize column names
    expected = {"Timestamp": "open_time", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    rename_map = {}
    for k, v in expected.items():
        if k in df.columns:
            rename_map[k] = v
        elif k.lower() in df.columns:
            rename_map[k.lower()] = v
    if rename_map:
        df = df.rename(columns=rename_map)

    if "open_time" not in df.columns:
        print(f"[WARN] {base_name}: missing 'Timestamp' column — skipping.")
        return

    df["open_time"] = pd.to_datetime(df["open_time"])
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if df.empty:
        print(f"[WARN] {base_name}: no data — skipping.")
        return

    # Reset index
    df = df.reset_index(drop=True)

    if len(df) < 10:
        print(f"[WARN] {base_name}: too few rows ({len(df)}) — skipping.")
        return

    # Take latest 100 candles (or all if less than 100)
    actual_window = min(WINDOW_SIZE, len(df))
    start_index = max(0, len(df) - actual_window)
    visible_df = df.iloc[start_index:start_index + actual_window].copy().reset_index(drop=True)

    print(f"[INFO] {base_name}: Using {len(visible_df)} candles (available: {len(df)}, requested: {WINDOW_SIZE})")

    # Calculate Bollinger Bands
    visible_df["bb_upper"], visible_df["bb_lower"] = calculate_bollinger_bands(visible_df)

    # Find swing points
    swing_lows, swing_highs = find_swing_points(visible_df, window=2, min_gap=MIN_GAP)
    last_low_idx = swing_lows[-1] if swing_lows else -1
    last_high_idx = swing_highs[-1] if swing_highs else -1

    trendline_logs = []

    # Create figure
    fig, ax = plt.subplots(figsize=(16, 8))
    fig.subplots_adjust(bottom=0.25)

    # ---- Plot all candles continuously ----
    for i in range(len(visible_df)):
        row = visible_df.iloc[i]
        color = 'green' if row['close'] >= row['open'] else 'red'
        
        # Plot high-low wick
        ax.plot([i, i], [row["low"], row["high"]], color=color, linewidth=1)
        # Plot open-close body
        ax.plot([i, i], [row["open"], row["close"]], color=color, linewidth=4)

    # Plot Bollinger Bands (continuous)
    ax.plot(range(len(visible_df)), visible_df["bb_upper"], linestyle='--', label='BB Upper', color='gray', alpha=0.7)
    ax.plot(range(len(visible_df)), visible_df["bb_lower"], linestyle='--', label='BB Lower', color='gray', alpha=0.7)

    # Mark swing points
    if swing_lows:
        ax.scatter(swing_lows, visible_df["low"].iloc[swing_lows], color='blue', s=50, label='Swing Low', zorder=5)
    if swing_highs:
        ax.scatter(swing_highs, visible_df["high"].iloc[swing_highs], color='orange', s=50, label='Swing High', zorder=5)

    # ---- Find and plot trendlines using index positions ----
    support_lines = find_valid_trendlines(visible_df, swing_lows, mode='low', price_buffer_pct=PRICE_BUFFER_PCT,
                                          max_intersections=BB_MAX_INTERSECTIONS, max_penetration_pct=BB_MAX_PENETRATION_PCT)
    for i, line in enumerate(support_lines):
        (idx1, idx2), slope, intercept, _ = line
        x1, x2 = idx1, idx2
        x2_ext = x2 + TRENDLINE_EXTENSION if idx1 == last_low_idx or idx2 == last_low_idx else x2
        xs, ys = [x1, x2_ext], [slope * x + intercept for x in [x1, x2_ext]]
        ax.plot(xs, ys, color='blue', linestyle='--', linewidth=2, label='Support' if i == 0 else "")
        is_extended = TRENDLINE_EXTENSION if idx1 == last_low_idx or idx2 == last_low_idx else 0
        log_trendline(trendline_logs, "support", idx1, idx2, slope, intercept, visible_df, extended=is_extended)

    resistance_lines = find_valid_trendlines(visible_df, swing_highs, mode='high', price_buffer_pct=PRICE_BUFFER_PCT,
                                             max_intersections=BB_MAX_INTERSECTIONS, max_penetration_pct=BB_MAX_PENETRATION_PCT)
    for i, line in enumerate(resistance_lines):
        (idx1, idx2), slope, intercept, _ = line
        x1, x2 = idx1, idx2
        x2_ext = x2 + TRENDLINE_EXTENSION if idx1 == last_high_idx or idx2 == last_high_idx else x2
        xs, ys = [x1, x2_ext], [slope * x + intercept for x in [x1, x2_ext]]
        ax.plot(xs, ys, color='orange', linestyle='--', linewidth=2, label='Resistance' if i == 0 else "")
        is_extended = TRENDLINE_EXTENSION if idx1 == last_high_idx or idx2 == last_high_idx else 0
        log_trendline(trendline_logs, "resistance", idx1, idx2, slope, intercept, visible_df, extended=is_extended)

    # BB-filtered lines and strict trendlines
    draw_bb_filtered_lines(ax, visible_df, swing_lows, 'low', 'cyan', last_low_idx, trendline_logs,
                           5, steps=BB_CHECK_STEPS, max_intersections=BB_MAX_INTERSECTIONS,
                           max_penetration_pct=BB_MAX_PENETRATION_PCT, extension=TRENDLINE_EXTENSION)
    draw_bb_filtered_lines(ax, visible_df, swing_highs, 'high', 'magenta', last_high_idx, trendline_logs,
                           5, steps=BB_CHECK_STEPS, max_intersections=BB_MAX_INTERSECTIONS,
                           max_penetration_pct=BB_MAX_PENETRATION_PCT, extension=TRENDLINE_EXTENSION)

    find_strict_trendline_from_latest_swing(ax, visible_df, swing_highs, 'high', last_high_idx, 'deeppink',
                                            'Strict High Line', trendline_logs, 5,
                                            extend_candles=TRENDLINE_EXTENSION, price_buffer_pct=PRICE_BUFFER_PCT)
    find_strict_trendline_from_latest_swing(ax, visible_df, swing_lows, 'low', last_low_idx, 'darkgreen',
                                            'Strict Low Line', trendline_logs, 5,
                                            extend_candles=TRENDLINE_EXTENSION, price_buffer_pct=PRICE_BUFFER_PCT)


    # ---- IMPROVED TIMESTAMP DISPLAY WITH LATEST CANDLE PROMINENT ----
    day_starts = []
    day_info = []
    
    current_date = None
    for i in range(len(visible_df)):
        candle_time = visible_df["open_time"].iloc[i]
        candle_date = candle_time.date()
        
        if candle_date != current_date:
            day_starts.append(i)
            day_info.append({
                'index': i,
                'date': candle_date,
                'first_candle_time': candle_time.strftime("%H:%M")
            })
            current_date = candle_date
    
    # Get latest candle timestamp for prominent display
    latest_candle_time = visible_df["open_time"].iloc[-1]
    latest_candle_str = latest_candle_time.strftime("%Y-%m-%d %H:%M")
    
    # Set x-axis ticks - ensure latest candle is always marked
    all_ticks = []
    all_labels = []
    
    # Add day start ticks
    for info in day_info:
        all_ticks.append(info['index'])
        all_labels.append(f"{info['date'].strftime('%m/%d')}\n{info['first_candle_time']}")
    
    # ALWAYS ADD LATEST CANDLE TICK
    if len(visible_df) - 1 not in all_ticks:  # If latest candle isn't already a day start
        all_ticks.append(len(visible_df) - 1)
        all_labels.append(f"LATEST\n{latest_candle_time.strftime('%H:%M')}")
    
    # Add a few intermediate ticks for context (every 15-20 candles)
    tick_interval = max(1, len(visible_df) // 8)  # About 8 ticks total including start, latest, and intermediates
    intermediate_ticks = list(range(0, len(visible_df), tick_interval))
    
    for tick in intermediate_ticks:
        if tick not in all_ticks and tick != len(visible_df) - 1:  # Don't duplicate
            all_ticks.append(tick)
            candle_time = visible_df["open_time"].iloc[tick]
            all_labels.append(candle_time.strftime("%H:%M"))
    
    # Sort ticks and labels
    sorted_indices = sorted(range(len(all_ticks)), key=lambda i: all_ticks[i])
    all_ticks = [all_ticks[i] for i in sorted_indices]
    all_labels = [all_labels[i] for i in sorted_indices]
    
    # Set x-axis ticks and labels
    ax.set_xticks(all_ticks)
    ax.set_xticklabels(all_labels, rotation=45, ha='right', fontsize=8)
    
    # Highlight the latest candle tick with a different color
    latest_tick_index = all_ticks.index(len(visible_df) - 1) if (len(visible_df) - 1) in all_ticks else -1
    if latest_tick_index != -1:
        labels = ax.get_xticklabels()
        labels[latest_tick_index].set_color('red')
        labels[latest_tick_index].set_fontweight('bold')
    
    # Add vertical lines at day starts for better visualization
    for day_start in day_starts:
        ax.axvline(x=day_start, color='gray', linestyle=':', alpha=0.4, linewidth=1)
    
    # Add a prominent vertical line at the latest candle
    ax.axvline(x=len(visible_df) - 1, color='red', linestyle='-', alpha=0.6, linewidth=1.5)
    
    # Add background color alternating for days
    for i in range(len(day_starts)):
        start_idx = day_starts[i]
        end_idx = day_starts[i + 1] if i < len(day_starts) - 1 else len(visible_df)
        
        if i % 2 == 0:
            ax.axvspan(start_idx - 0.5, end_idx - 0.5, alpha=0.05, color='blue')
        else:
            ax.axvspan(start_idx - 0.5, end_idx - 0.5, alpha=0.05, color='gray')

    # Chart formatting with prominent latest candle info
    start_date = visible_df["open_time"].iloc[0].strftime("%Y-%m-%d")
    end_date = visible_df["open_time"].iloc[-1].strftime("%Y-%m-%d")
    
    # Add latest candle info to title
    latest_price = visible_df["close"].iloc[-1]
    title = f"{base_name} | {len(visible_df)} Candles | Latest: {latest_candle_str} | Close: {latest_price:.2f}"
    
    ax.set_title(title, fontsize=12, pad=20)
    ax.set_xlabel(f"Time (Latest: {latest_candle_str})", fontsize=10)
    ax.set_ylabel("Price", fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Improve legend placement
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0., fontsize=9)

    # Save outputs
    chart_path = os.path.join(OUTPUT_DIR, f"{base_name}.png")
    log_path = os.path.join(LOG_DIR, f"{base_name}_trendline_log.csv")
    pd.DataFrame(trendline_logs).to_csv(log_path, index=False)
    plt.savefig(chart_path, bbox_inches='tight', dpi=150, facecolor='white')
    plt.close(fig)
    
    # Print summary info with latest candle
    day_count = len(day_starts)
    print(f"[✅] {base_name} → {len(visible_df)} candles | {day_count} trading days | Latest: {latest_candle_str} | Close: {latest_price:.2f}")


# ----------------- batch run -----------------
def batch_process_all():
    if not os.path.isdir(INPUT_DIR):
        print(f"[ERROR] Input folder not found: {INPUT_DIR}")
        return
    csv_files = [os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR) if f.lower().endswith(".csv")]
    if not csv_files:
        print(f"[WARN] No CSV files in {INPUT_DIR}")
        return
    for csv_file in csv_files:
        try:
            analyze_symbol(csv_file)
        except Exception as e:
            print(f"[ERROR] processing {csv_file}: {e}")

if __name__ == "__main__":
    batch_process_all()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
# # ===============================================
# # FOR 24 HR RUNNING STOCKS
# # ===============================================

# #!/usr/bin/env python3
# import os
# import sys
# import pandas as pd
# import matplotlib.pyplot as plt
# import matplotlib.dates as mdates
# from datetime import timedelta

# # Ensure UTF-8 prints (optional)
# try:
#     sys.stdout.reconfigure(encoding="utf-8")
# except Exception:
#     pass

# # --------- CONFIG ----------
# INPUT_DIR = "symbols_ohlcv"
# OUTPUT_DIR = "trendlined_symbols"
# LOG_DIR = "trendline_logs"

# WINDOW_SIZE = 100
# PRICE_BUFFER = 10            # how close a swing point must be to the line (price units)
# MIN_GAP = 4                  # minimum gap (in candles) between swing points
# TRENDLINE_EXTENSION = 20     # how many candles to extend the latest trendlines by
# BB_CHECK_STEPS = 3
# BB_MAX_INTERSECTIONS = 1
# BB_MAX_PENETRATION = 10.0    # price units allowed when testing intersections
# VALID_TOUCHES_MIN = 3

# os.makedirs(OUTPUT_DIR, exist_ok=True)
# os.makedirs(LOG_DIR, exist_ok=True)

# # ----------------- helpers -----------------
# def calculate_bollinger_bands(df, length=20, mult=2.0):
#     basis = df["close"].rolling(window=length, min_periods=1).mean()
#     stdev = df["close"].rolling(window=length, min_periods=1).std(ddof=0)
#     upper = basis + mult * stdev
#     lower = basis - mult * stdev
#     return upper, lower

# def extend_time(ts, minutes_per_candle=5, steps=30):
#     return ts + timedelta(minutes=minutes_per_candle * steps)

# def find_swing_points(df, window=2, min_gap=3, tolerance=0.0):
#     swing_lows, swing_highs = [], []
#     last_low_idx, last_high_idx = -min_gap - 1, -min_gap - 1
#     L = len(df)
#     for i in range(window, L - window):
#         local_lows = df["low"].iloc[i - window:i + window + 1]
#         local_highs = df["high"].iloc[i - window:i + window + 1]
#         current_low = df["low"].iloc[i]
#         current_high = df["high"].iloc[i]
#         if abs(current_low - local_lows.min()) <= tolerance and (i - last_low_idx) > min_gap:
#             swing_lows.append(i)
#             last_low_idx = i
#         if abs(current_high - local_highs.max()) <= tolerance and (i - last_high_idx) > min_gap:
#             swing_highs.append(i)
#             last_high_idx = i
#     return swing_lows, swing_highs

# def log_trendline(logs, line_type, idx1, idx2, slope, intercept, df, extended=0):
#     t1 = df["open_time"].iloc[idx1]
#     t2 = df["open_time"].iloc[idx2]
#     price_col = "low" if ("low" in line_type.lower() or "support" in line_type.lower()) else "high"
#     p1 = float(df[price_col].iloc[idx1])
#     p2 = float(df[price_col].iloc[idx2])
#     norm_type = "support" if ("low" in line_type.lower() or "support" in line_type.lower()) else \
#                 ("resistance" if ("high" in line_type.lower() or "resistance" in line_type.lower()) else line_type.lower())
#     logs.append({
#         "type": norm_type,
#         "x1_time": pd.Timestamp(t1).isoformat(),
#         "x2_time": pd.Timestamp(t2).isoformat(),
#         "y1_price": p1,
#         "y2_price": p2,
#         "slope": slope,
#         "intercept": intercept,
#         "extended": int(extended)
#     })

# def find_valid_trendlines(df, swing_indices, mode='low', price_buffer=10, max_intersections=1, max_penetration=20.0):
#     valid_lines = []
#     n = len(swing_indices)
#     if n < 2:
#         return valid_lines

#     for i in range(n - 1):
#         for j in range(i + 1, n):
#             idx1, idx2 = swing_indices[i], swing_indices[j]
#             x1 = df["open_time"].iloc[idx1].timestamp()
#             y1 = df[mode].iloc[idx1]
#             x2 = df["open_time"].iloc[idx2].timestamp()
#             y2 = df[mode].iloc[idx2]
#             if x1 == x2:
#                 continue
#             slope = (y2 - y1) / (x2 - x1)
#             intercept = y1 - slope * x1

#             # how many swing points (other than the pair) are within price_buffer
#             touches = 2
#             for k in range(n):
#                 if k == i or k == j:
#                     continue
#                 idxk = swing_indices[k]
#                 xk = df["open_time"].iloc[idxk].timestamp()
#                 yk = df[mode].iloc[idxk]
#                 y_on_line = slope * xk + intercept
#                 if abs(yk - y_on_line) <= price_buffer:
#                     touches += 1

#             # intersections: check body midpoints across visible df
#             intersections = 0
#             total_penetration = 0.0
#             for m in range(len(df)):
#                 x_m = df["open_time"].iloc[m].timestamp()
#                 y_m = slope * x_m + intercept
#                 open_price = df["open"].iloc[m]
#                 close_price = df["close"].iloc[m]
#                 body_mid = (open_price + close_price) / 2
#                 penetration = abs(y_m - body_mid)
#                 if penetration <= max_penetration:
#                     intersections += 1
#                     total_penetration += penetration

#             if touches >= VALID_TOUCHES_MIN and intersections <= max_intersections:
#                 valid_lines.append(((idx1, idx2), slope, intercept, touches))

#     return valid_lines

# def filter_trendline_by_bollinger(line, df, after_idx, steps=3):
#     # ensure trendline is within BB for the next few steps after after_idx
#     _, slope, intercept, _ = line
#     max_idx = min(after_idx + steps, len(df) - 1)
#     for i in range(after_idx + 1, max_idx + 1):
#         x = df["open_time"].iloc[i].timestamp()
#         y = slope * x + intercept
#         if pd.isna(df["bb_lower"].iloc[i]) or pd.isna(df["bb_upper"].iloc[i]):
#             return False
#         if y < df["bb_lower"].iloc[i] or y > df["bb_upper"].iloc[i]:
#             return False
#     return True

# # Advanced BB-filtered line finder (mirrors your earlier function)
# def draw_bb_filtered_lines(ax, df, swing_indices, mode, color, last_idx, logs, candle_interval_minutes, steps=3, max_intersections=1, max_penetration=10.0, extension=20):
#     if not swing_indices or last_idx < 0 or last_idx >= len(df):
#         return

#     best_line = None
#     best_score = float('inf')

#     # Step 1: try BB-filtered lines (from previous swing -> last_idx)
#     for i in range(len(swing_indices) - 1):
#         idx1 = swing_indices[i]
#         idx2 = last_idx
#         if idx1 >= idx2:
#             continue
#         x1 = df["open_time"].iloc[idx1].timestamp()
#         y1 = df[mode].iloc[idx1]
#         x2 = df["open_time"].iloc[idx2].timestamp()
#         y2 = df[mode].iloc[idx2]
#         if x1 == x2:
#             continue
#         slope = (y2 - y1) / (x2 - x1)
#         intercept = y1 - slope * x1
#         virtual_line = ((idx1, idx2), slope, intercept, 0)

#         if not filter_trendline_by_bollinger(virtual_line, df, last_idx, steps):
#             continue

#         intersections, total_penetration = 0, 0.0
#         for j in range(last_idx + 1, min(last_idx + steps + 1, len(df))):
#             t = df["open_time"].iloc[j].timestamp()
#             y_line = slope * t + intercept
#             body_mid = (df["open"].iloc[j] + df["close"].iloc[j]) / 2
#             penetration = abs(y_line - body_mid)
#             if penetration <= max_penetration:
#                 intersections += 1
#                 total_penetration += penetration

#         if intersections > max_intersections:
#             continue

#         avg_penetration = (total_penetration / intersections) if intersections > 0 else float('inf')
#         if avg_penetration < best_score:
#             best_score = avg_penetration
#             best_line = ((idx1, idx2), slope, intercept)

#     # Step 2: plot BB-best line if found
#     if best_line:
#         (idx1, idx2), slope, intercept = best_line
#         x1dt = df["open_time"].iloc[idx1]
#         x2dt = extend_time(df["open_time"].iloc[idx2], candle_interval_minutes, extension)
#         xs = [x1dt, x2dt]
#         ys = [slope * x.timestamp() + intercept for x in xs]
#         ax.plot(xs, ys, linestyle='-', linewidth=2.5, color=color, label=f'BB Best {mode.capitalize()}')
#         log_trendline(logs, f'BB Best {mode.capitalize()}', idx1, idx2, slope, intercept, df, extended=extension)
#         return

#     # Step 3: fallback validated line(s)
#     fallback_candidates = [idx for idx in swing_indices if idx != last_idx]
#     if not fallback_candidates:
#         return

#     def get_extreme(candidates):
#         return min(candidates, key=lambda i: df["low"].iloc[i]) if mode == 'low' \
#             else max(candidates, key=lambda i: df["high"].iloc[i])

#     def validate_fallback(extreme_idx):
#         x1 = df["open_time"].iloc[extreme_idx].timestamp()
#         y1 = df[mode].iloc[extreme_idx]
#         x2 = df["open_time"].iloc[last_idx].timestamp()
#         y2 = df[mode].iloc[last_idx]
#         if x1 == x2:
#             return None
#         slope = (y2 - y1) / (x2 - x1)
#         intercept = y1 - slope * x1
#         intersections, total_penetration = 0, 0.0
#         for j in range(last_idx + 1, min(last_idx + steps + 1, len(df))):
#             t = df["open_time"].iloc[j].timestamp()
#             y_line = slope * t + intercept
#             body_mid = (df["open"].iloc[j] + df["close"].iloc[j]) / 2
#             penetration = abs(y_line - body_mid)
#             if penetration <= max_penetration:
#                 intersections += 1
#                 total_penetration += penetration
#         if intersections <= max_intersections:
#             return slope, intercept, extreme_idx
#         return None

#     extreme_idx = get_extreme(fallback_candidates)
#     result = validate_fallback(extreme_idx)
#     if result is None and len(fallback_candidates) > 1:
#         filtered = [i for i in fallback_candidates if i != extreme_idx]
#         second_extreme_idx = get_extreme(filtered)
#         result = validate_fallback(second_extreme_idx)
#         if result:
#             extreme_idx = second_extreme_idx

#     if result:
#         slope, intercept, extreme_idx = result
#         x1dt = df["open_time"].iloc[extreme_idx]
#         x2dt = extend_time(df["open_time"].iloc[last_idx], candle_interval_minutes, extension)
#         xs = [x1dt, x2dt]
#         ys = [slope * x.timestamp() + intercept for x in xs]
#         ax.plot(xs, ys, linestyle=':', linewidth=2, color=color, label=f'{mode.capitalize()} Fallback')
#         log_trendline(logs, f'{mode.capitalize()} Fallback', extreme_idx, last_idx, slope, intercept, df, extended=extension)

# def find_strict_trendline_from_latest_swing(ax, df, swing_indices, mode, last_idx, color, label_name, logs, candle_interval_minutes, extend_candles=20):
#     if not swing_indices or last_idx < 0 or last_idx >= len(df):
#         return
#     x2 = df["open_time"].iloc[last_idx].timestamp()
#     y2 = df[mode].iloc[last_idx]
#     for idx1 in swing_indices:
#         if idx1 >= last_idx:
#             continue
#         x1 = df["open_time"].iloc[idx1].timestamp()
#         y1 = df[mode].iloc[idx1]
#         # require directionality
#         if mode == 'high' and y1 <= y2:
#             continue
#         if mode == 'low' and y1 >= y2:
#             continue
#         slope = (y2 - y1) / (x2 - x1)
#         intercept = y1 - slope * x1
#         valid = True
#         for mid_idx in swing_indices:
#             if mid_idx <= idx1 or mid_idx >= last_idx:
#                 continue
#             t = df["open_time"].iloc[mid_idx].timestamp()
#             y_line = slope * t + intercept
#             open_p = df["open"].iloc[mid_idx]
#             close_p = df["close"].iloc[mid_idx]
#             body_mid = (open_p + close_p) / 2
#             if mode == 'high' and body_mid > y_line:
#                 valid = False
#                 break
#             if mode == 'low' and body_mid < y_line:
#                 valid = False
#                 break
#         if valid:
#             x1dt = df["open_time"].iloc[idx1]
#             x2dt = df["open_time"].iloc[last_idx]
#             x2dt_ext = extend_time(x2dt, candle_interval_minutes, extend_candles)
#             xs = [x1dt, x2dt_ext]
#             ys = [slope * x.timestamp() + intercept for x in xs]
#             ax.plot(xs, ys, linestyle='-', linewidth=2.8, color=color, label=label_name)
#             log_trendline(logs, label_name, idx1, last_idx, slope, intercept, df, extended=extend_candles)
#             print(f"[🧭] Strict trendline found: {label_name} from index {idx1} to {last_idx}")
#             break

# # ----------------- per-symbol analysis -----------------
# # ===============================================
# # FOR 24 HR RUNNING STOCKS
# # ===============================================

# # def analyze_symbol(csv_path):
# #     base_name = os.path.basename(csv_path).rsplit(".", 1)[0]
# #     try:
# #         df = pd.read_csv(csv_path)
# #     except Exception as e:
# #         print(f"[ERROR] Cannot read {csv_path}: {e}")
# #         return

# #     # Standardize column names for this script
# #     expected = {"Timestamp": "open_time", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
# #     # Accept either exact header case or lowercase
# #     cols = {c: c for c in df.columns}
# #     # map if standard capitalized headers present
# #     rename_map = {}
# #     for k, v in expected.items():
# #         if k in df.columns:
# #             rename_map[k] = v
# #         elif k.lower() in df.columns:
# #             rename_map[k.lower()] = v
# #     if rename_map:
# #         df = df.rename(columns=rename_map)

# #     if "open_time" not in df.columns:
# #         print(f"[WARN] {base_name}: missing 'Timestamp' column — skipping.")
# #         return

# #     df["open_time"] = pd.to_datetime(df["open_time"])
# #     # cast OHLC to float
# #     for c in ["open", "high", "low", "close"]:
# #         df[c] = pd.to_numeric(df[c], errors="coerce")

# #     # enough rows?
# #     if len(df) < 10:
# #         print(f"[WARN] {base_name}: too few rows ({len(df)}) — skipping.")
# #         return

# #     start_index = max(0, len(df) - WINDOW_SIZE)
# #     visible_df = df.iloc[start_index:start_index + WINDOW_SIZE].copy().reset_index(drop=True)

# #     # compute Bollinger on visible window (and df if you want longer rolling)
# #     visible_df["bb_upper"], visible_df["bb_lower"] = calculate_bollinger_bands(visible_df)

# #     # detect candle interval in minutes
# #     if len(visible_df) >= 2:
# #         candle_interval_minutes = int((visible_df["open_time"].iloc[1] - visible_df["open_time"].iloc[0]).total_seconds() / 60) or 5
# #     else:
# #         candle_interval_minutes = 5

# #     swing_lows, swing_highs = find_swing_points(visible_df, window=2, min_gap=MIN_GAP)
# #     last_low_idx = swing_lows[-1] if swing_lows else -1
# #     last_high_idx = swing_highs[-1] if swing_highs else -1

# #     trendline_logs = []

# #     # --- plotting
# #     fig, ax = plt.subplots(figsize=(14, 7))
# #     fig.subplots_adjust(bottom=0.2)

# #     # draw candles (simple)
# #     for _, row in visible_df.iterrows():
# #         color = 'green' if row['close'] >= row['open'] else 'red'
# #         ax.plot([row["open_time"]] * 2, [row["low"], row["high"]], color=color, linewidth=1)
# #         ax.plot([row["open_time"]] * 2, [row["open"], row["close"]], color=color, linewidth=4)

# #     # bollinger
# #     ax.plot(visible_df["open_time"], visible_df["bb_upper"], linestyle='--', label='BB Upper')
# #     ax.plot(visible_df["open_time"], visible_df["bb_lower"], linestyle='--', label='BB Lower')

# #     # mark swing points
# #     if swing_lows:
# #         ax.scatter(visible_df["open_time"].iloc[swing_lows], visible_df["low"].iloc[swing_lows], color='blue', s=50, label='Swing Low')
# #     if swing_highs:
# #         ax.scatter(visible_df["open_time"].iloc[swing_highs], visible_df["high"].iloc[swing_highs], color='orange', s=50, label='Swing High')

# #     # --- valid trendlines from swing pairs (strict validation)
# #     support_lines = find_valid_trendlines(visible_df, swing_lows, mode='low', price_buffer=PRICE_BUFFER, max_intersections=BB_MAX_INTERSECTIONS, max_penetration=BB_MAX_PENETRATION)
# #     for i, line in enumerate(support_lines):
# #         (idx1, idx2), slope, intercept, _ = line
# #         x1 = visible_df["open_time"].iloc[idx1]
# #         x2 = visible_df["open_time"].iloc[idx2]
# #         x2_ext = extend_time(x2, candle_interval_minutes, TRENDLINE_EXTENSION) if idx1 == last_low_idx or idx2 == last_low_idx else x2
# #         xs = [x1, x2_ext]
# #         ys = [slope * x.timestamp() + intercept for x in xs]
# #         ax.plot(xs, ys, color='blue', linestyle='--', linewidth=2, label='Support' if i == 0 else "")
# #         is_extended = TRENDLINE_EXTENSION if idx1 == last_low_idx or idx2 == last_low_idx else 0
# #         log_trendline(trendline_logs, "support", idx1, idx2, slope, intercept, visible_df, extended=is_extended)

# #     resistance_lines = find_valid_trendlines(visible_df, swing_highs, mode='high', price_buffer=PRICE_BUFFER, max_intersections=BB_MAX_INTERSECTIONS, max_penetration=BB_MAX_PENETRATION)
# #     for i, line in enumerate(resistance_lines):
# #         (idx1, idx2), slope, intercept, _ = line
# #         x1 = visible_df["open_time"].iloc[idx1]
# #         x2 = visible_df["open_time"].iloc[idx2]
# #         x2_ext = extend_time(x2, candle_interval_minutes, TRENDLINE_EXTENSION) if idx1 == last_high_idx or idx2 == last_high_idx else x2
# #         xs = [x1, x2_ext]
# #         ys = [slope * x.timestamp() + intercept for x in xs]
# #         ax.plot(xs, ys, color='orange', linestyle='--', linewidth=2, label='Resistance' if i == 0 else "")
# #         is_extended = TRENDLINE_EXTENSION if idx1 == last_high_idx or idx2 == last_high_idx else 0
# #         log_trendline(trendline_logs, "resistance", idx1, idx2, slope, intercept, visible_df, extended=is_extended)

# #     # --- BB-filtered extras (best line / fallback)
# #     draw_bb_filtered_lines(ax, visible_df, swing_lows, 'low', 'cyan', last_low_idx, trendline_logs, candle_interval_minutes, steps=BB_CHECK_STEPS, max_intersections=BB_MAX_INTERSECTIONS, max_penetration=BB_MAX_PENETRATION, extension=TRENDLINE_EXTENSION)
# #     draw_bb_filtered_lines(ax, visible_df, swing_highs, 'high', 'magenta', last_high_idx, trendline_logs, candle_interval_minutes, steps=BB_CHECK_STEPS, max_intersections=BB_MAX_INTERSECTIONS, max_penetration=BB_MAX_PENETRATION, extension=TRENDLINE_EXTENSION)

# #     # --- strict trendlines from latest swing
# #     find_strict_trendline_from_latest_swing(ax, visible_df, swing_highs, 'high', last_high_idx, 'deeppink', 'Strict High Line', trendline_logs, candle_interval_minutes, extend_candles=TRENDLINE_EXTENSION)
# #     find_strict_trendline_from_latest_swing(ax, visible_df, swing_lows, 'low', last_low_idx, 'darkgreen', 'Strict Low Line', trendline_logs, candle_interval_minutes, extend_candles=TRENDLINE_EXTENSION)

# #     # chart formatting
# #     ax.set_title(f"{base_name} | Trendlines + Bollinger Bands")
# #     ax.set_xlabel("Time")
# #     ax.set_ylabel("Price")
# #     ax.grid(True)
# #     ax.legend()
# #     ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
# #     fig.autofmt_xdate()

# #     # save outputs
# #     chart_path = os.path.join(OUTPUT_DIR, f"{base_name}.png")
# #     log_path = os.path.join(LOG_DIR, f"{base_name}_trendline_log.csv")
# #     pd.DataFrame(trendline_logs).to_csv(log_path, index=False)
# #     plt.savefig(chart_path)
# #     plt.close(fig)
# #     print(f"[✅] {base_name} → chart: {chart_path}, log: {log_path}")



# # ----------------- batch run -----------------
# def batch_process_all():
#     if not os.path.isdir(INPUT_DIR):
#         print(f"[ERROR] Input folder not found: {INPUT_DIR}")
#         return
#     csv_files = [os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR) if f.lower().endswith(".csv")]
#     if not csv_files:
#         print(f"[WARN] No CSV files in {INPUT_DIR}")
#         return
#     for csv_file in csv_files:
#         try:
#             analyze_symbol(csv_file)
#         except Exception as e:
#             print(f"[ERROR] processing {csv_file}: {e}")

# if __name__ == "__main__":
#     batch_process_all()



