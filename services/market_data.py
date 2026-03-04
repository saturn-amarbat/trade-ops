"""
market_data.py — Alpaca API wrapper for candles, snapshots, and streaming.
Handles all data fetching so other modules never touch the API directly.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import (
    StockBarsRequest,
    StockSnapshotRequest,
    StockLatestQuoteRequest,
)
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.data.live import StockDataStream


def get_client() -> StockHistoricalDataClient:
    """Return authenticated Alpaca historical data client."""
    return StockHistoricalDataClient(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_SECRET_KEY"),
    )


def get_stream() -> StockDataStream:
    """Return authenticated Alpaca websocket stream client."""
    return StockDataStream(
        api_key=os.getenv("ALPACA_API_KEY"),
        secret_key=os.getenv("ALPACA_SECRET_KEY"),
    )


def fetch_bars(
    symbol: str,
    timeframe: str = "1Min",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    limit: int = 500,
) -> pd.DataFrame:
    """
    Fetch OHLCV bars for a symbol.
    
    Args:
        symbol: Stock ticker (e.g. "AAPL")
        timeframe: "1Min", "5Min", "15Min", "1Hour", "1Day"
        start: Start datetime (default: today open)
        end: End datetime (default: now)
        limit: Max bars to return
    
    Returns:
        DataFrame with columns: open, high, low, close, volume, vwap, trade_count
    """
    client = get_client()
    
    tf_map = {
        "1Min": TimeFrame(1, TimeFrameUnit.Minute),
        "5Min": TimeFrame(5, TimeFrameUnit.Minute),
        "15Min": TimeFrame(15, TimeFrameUnit.Minute),
        "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
        "1Day": TimeFrame(1, TimeFrameUnit.Day),
    }
    
    if start is None:
        start = datetime.now().replace(hour=8, minute=30, second=0, microsecond=0)
    if end is None:
        end = datetime.now()
    
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf_map.get(timeframe, tf_map["1Min"]),
        start=start,
        end=end,
        limit=limit,
    )
    
    bars = client.get_stock_bars(request)
    df = bars.df
    
    if isinstance(df.index, pd.MultiIndex):
        df = df.loc[symbol]
    
    df.index = pd.to_datetime(df.index)
    return df


def fetch_snapshots(symbols: list[str]) -> dict:
    """
    Fetch current snapshots (latest quote, latest trade, minute bar, daily bar, prev daily bar)
    for a list of symbols.
    
    Returns:
        dict mapping symbol -> snapshot data dict
    """
    client = get_client()
    request = StockSnapshotRequest(symbol_or_symbols=symbols)
    snapshots = client.get_stock_snapshot(request)
    
    result = {}
    for sym, snap in snapshots.items():
        result[sym] = {
            "latest_trade_price": snap.latest_trade.price if snap.latest_trade else None,
            "latest_trade_size": snap.latest_trade.size if snap.latest_trade else None,
            "prev_daily_close": snap.previous_daily_bar.close if snap.previous_daily_bar else None,
            "prev_daily_volume": snap.previous_daily_bar.volume if snap.previous_daily_bar else None,
            "daily_open": snap.daily_bar.open if snap.daily_bar else None,
            "daily_high": snap.daily_bar.high if snap.daily_bar else None,
            "daily_low": snap.daily_bar.low if snap.daily_bar else None,
            "daily_close": snap.daily_bar.close if snap.daily_bar else None,
            "daily_volume": snap.daily_bar.volume if snap.daily_bar else None,
            "minute_close": snap.minute_bar.close if snap.minute_bar else None,
            "minute_volume": snap.minute_bar.volume if snap.minute_bar else None,
        }
    return result


def fetch_historical_daily(
    symbol: str, days: int = 30
) -> pd.DataFrame:
    """Fetch N days of daily bars for a symbol (for RVOL calculation)."""
    client = get_client()
    end = datetime.now()
    start = end - timedelta(days=days + 5)  # buffer for weekends
    
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame(1, TimeFrameUnit.Day),
        start=start,
        end=end,
    )
    
    bars = client.get_stock_bars(request)
    df = bars.df
    
    if isinstance(df.index, pd.MultiIndex):
        df = df.loc[symbol]
    
    return df.tail(days)
