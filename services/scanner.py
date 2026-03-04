"""
scanner.py — Premarket gapper scanner.
Finds stocks that meet Ross Cameron's universe criteria:
  - Price $2-$20
  - Gap up >= 10%
  - High relative volume (5x+)
  - Low float preferred (<20M)
"""

import yaml
import pandas as pd
from services.market_data import fetch_snapshots, fetch_historical_daily


def load_config() -> dict:
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)


def get_seed_tickers() -> list[str]:
    """
    Get a broad list of tickers to scan.
    
    Strategy: We use Alpaca's active assets endpoint
    to get all tradeable US equities.
    """
    import os
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetAssetsRequest
    from alpaca.trading.enums import AssetClass, AssetStatus
    
    client = TradingClient(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_SECRET_KEY"),
        paper=True,
    )
    
    request = GetAssetsRequest(
        asset_class=AssetClass.US_EQUITY,
        status=AssetStatus.ACTIVE,
    )
    assets = client.get_all_assets(request)
    
    tickers = [
        a.symbol for a in assets
        if a.tradable and a.easy_to_borrow and len(a.symbol) <= 5
    ]
    
    return tickers


def scan_premarket(seed_tickers: list[str] = None) -> pd.DataFrame:
    """
    Scan for premarket gappers matching Ross Cameron's universe filters.
    
    Returns DataFrame with columns:
        symbol, price, prev_close, gap_pct, daily_volume, rvol, score
    """
    config = load_config()["universe"]
    
    if seed_tickers is None:
        seed_tickers = get_seed_tickers()
    
    # Fetch snapshots in batches (Alpaca limit)
    batch_size = 100
    all_snapshots = {}
    for i in range(0, len(seed_tickers), batch_size):
        batch = seed_tickers[i:i + batch_size]
        try:
            snaps = fetch_snapshots(batch)
            all_snapshots.update(snaps)
        except Exception as e:
            print(f"  Snapshot batch error: {e}")
            continue
    
    candidates = []
    for sym, data in all_snapshots.items():
        price = data.get("latest_trade_price") or data.get("daily_close")
        prev_close = data.get("prev_daily_close")
        volume = data.get("daily_volume", 0) or 0
        
        if not price or not prev_close or prev_close == 0:
            continue
        
        gap_pct = ((price - prev_close) / prev_close) * 100
        
        # Apply universe filters
        if price < config["price_min"] or price > config["price_max"]:
            continue
        if gap_pct < config["gap_pct_min"]:
            continue
        if volume < config.get("min_premarket_volume", 0):
            continue
        
        candidates.append({
            "symbol": sym,
            "price": round(price, 2),
            "prev_close": round(prev_close, 2),
            "gap_pct": round(gap_pct, 1),
            "volume": volume,
        })
    
    if not candidates:
        return pd.DataFrame()
    
    df = pd.DataFrame(candidates)
    
    # Calculate RVOL for top candidates (API-intensive, so limit)
    df = df.nlargest(30, "gap_pct")
    
    rvol_values = []
    for sym in df["symbol"]:
        try:
            hist = fetch_historical_daily(sym, days=20)
            avg_vol = hist["volume"].mean()
            current_vol = df.loc[df["symbol"] == sym, "volume"].iloc[0]
            rvol = current_vol / avg_vol if avg_vol > 0 else 0
            rvol_values.append(round(rvol, 1))
        except Exception:
            rvol_values.append(0)
    
    df["rvol"] = rvol_values
    
    # Filter by RVOL
    df = df[df["rvol"] >= config["rvol_min"]]
    
    # Score: higher gap + higher rvol = better
    if not df.empty:
        df["score"] = (df["gap_pct"] * 0.4) + (df["rvol"] * 0.6)
        df = df.sort_values("score", ascending=False).reset_index(drop=True)
    
    return df
