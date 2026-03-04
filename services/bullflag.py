"""
bullflag.py — Bull flag pattern detection engine.

Ross Cameron's bull flag rules (encoded):
1. Impulse leg UP: price rises X% over Y candles with volume spike
2. Pullback (flag): price pulls back <=25% of impulse, lower volume, >=2 candles
3. Trigger: first candle to make a new high vs prior candle
4. Stop: low of the pullback
5. Target: retest of high-of-day, then continuation
6. Volume: green candles loud on push, red candles quiet on pullback
"""

import yaml
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class BullFlagSetup:
    """Represents a detected bull flag setup."""
    symbol: str
    timeframe: str
    impulse_start_idx: int
    impulse_end_idx: int      # = swing high candle
    pullback_end_idx: int     # = last pullback candle
    trigger_idx: int          # = breakout candle
    
    impulse_low: float        # bottom of impulse leg
    impulse_high: float       # top of impulse (swing high H)
    pullback_low: float       # lowest point of pullback = STOP
    trigger_price: float      # high of last pullback candle = ENTRY
    
    impulse_pct: float        # % move of impulse
    pullback_depth_pct: float # pullback as % of impulse range
    volume_ratio: float       # impulse avg vol / pullback avg vol
    
    entry: float
    stop: float
    target_1: float           # retest of impulse high (HOD)
    target_2: float           # 2R extension
    risk: float
    reward: float
    rr_ratio: float
    
    quality_score: float      # 0-100 composite score
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "entry": self.entry,
            "stop": self.stop,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "risk": round(self.risk, 3),
            "reward": round(self.reward, 3),
            "rr_ratio": round(self.rr_ratio, 2),
            "impulse_pct": round(self.impulse_pct, 1),
            "pullback_depth_pct": round(self.pullback_depth_pct, 1),
            "volume_ratio": round(self.volume_ratio, 1),
            "quality_score": round(self.quality_score, 1),
        }


def load_config() -> dict:
    with open("config/settings.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    return cfg["bullflag"]


def detect_impulse_legs(df: pd.DataFrame, config: dict) -> list[dict]:
    """
    Find all impulse legs (strong upward moves) in the candle data.
    
    An impulse leg is a sequence of candles where:
    - Price rises at least impulse_min_pct %
    - Duration is between impulse_min_candles and impulse_max_candles
    - Volume is elevated compared to surrounding candles
    """
    min_pct = config["impulse_min_pct"]
    min_candles = config["impulse_min_candles"]
    max_candles = config["impulse_max_candles"]
    
    legs = []
    n = len(df)
    
    for i in range(n - min_candles):
        low_point = df["low"].iloc[i]
        
        for j in range(i + min_candles, min(i + max_candles + 1, n)):
            high_point = df["high"].iloc[i:j+1].max()
            high_idx = df["high"].iloc[i:j+1].idxmax()
            pct_move = ((high_point - low_point) / low_point) * 100
            
            if pct_move >= min_pct:
                avg_vol = df["volume"].iloc[i:j+1].mean()
                legs.append({
                    "start_idx": i,
                    "end_idx": df.index.get_loc(high_idx) if isinstance(high_idx, pd.Timestamp) else j,
                    "low": low_point,
                    "high": high_point,
                    "pct": pct_move,
                    "avg_volume": avg_vol,
                })
                break  # Take the first qualifying window from this start
    
    # De-duplicate overlapping legs — keep the strongest
    if not legs:
        return legs
    
    filtered = [legs[0]]
    for leg in legs[1:]:
        prev = filtered[-1]
        if leg["start_idx"] > prev["end_idx"]:
            filtered.append(leg)
        elif leg["pct"] > prev["pct"]:
            filtered[-1] = leg
    
    return filtered


def detect_pullback(
    df: pd.DataFrame, impulse: dict, config: dict
) -> Optional[dict]:
    """
    After an impulse leg, detect a valid pullback (flag).
    
    Valid pullback:
    - Starts after impulse high
    - At least min_pullback_candles candles
    - Pullback depth <= pullback_max_pct of impulse range
    - Volume lighter than impulse average
    """
    start = impulse["end_idx"] + 1
    max_candles = config["max_pullback_candles"]
    min_candles = config["min_pullback_candles"]
    max_depth = config["pullback_max_pct"]
    hard_cut = config["pullback_hard_cut"]
    impulse_range = impulse["high"] - impulse["low"]
    
    if start >= len(df) or impulse_range <= 0:
        return None
    
    end = min(start + max_candles, len(df))
    
    if end - start < min_candles:
        return None
    
    pullback_slice = df.iloc[start:end]
    pullback_low = pullback_slice["low"].min()
    pullback_depth = impulse["high"] - pullback_low
    pullback_depth_pct = (pullback_depth / impulse_range) * 100
    
    # Hard cut
    if pullback_depth_pct > hard_cut:
        return None
    
    # Soft filter
    if pullback_depth_pct > max_depth:
        return None
    
    # Volume check: pullback volume should be lighter
    pullback_avg_vol = pullback_slice["volume"].mean()
    vol_ratio = impulse["avg_volume"] / pullback_avg_vol if pullback_avg_vol > 0 else 0
    
    if vol_ratio < config["volume_ratio_min"]:
        return None
    
    # Find the end of pullback = last candle before a new high is made
    pb_end_idx = start
    for k in range(start + 1, end):
        if df["high"].iloc[k] > df["high"].iloc[k - 1]:
            # This candle made a new high — it's the trigger
            return {
                "start_idx": start,
                "end_idx": k - 1,
                "trigger_idx": k,
                "pullback_low": pullback_low,
                "pullback_depth_pct": pullback_depth_pct,
                "avg_volume": pullback_avg_vol,
                "volume_ratio": vol_ratio,
                "trigger_price": df["high"].iloc[k - 1],
            }
        pb_end_idx = k
    
    return None  # No trigger candle found yet


def compute_setup(
    symbol: str,
    timeframe: str,
    df: pd.DataFrame,
    impulse: dict,
    pullback: dict,
    config: dict,
) -> Optional[BullFlagSetup]:
    """
    Given a valid impulse + pullback, compute the full trade setup.
    
    Entry = break above last pullback candle high
    Stop = pullback low
    Target 1 = retest of impulse high (HOD)
    Target 2 = 2R above entry
    """
    risk_config = yaml.safe_load(open("config/settings.yaml"))["risk"]
    
    entry = pullback["trigger_price"]
    stop = pullback["pullback_low"]
    risk = entry - stop
    
    if risk <= 0:
        return None
    
    target_1 = impulse["high"]
    reward_1 = target_1 - entry
    target_2 = entry + (risk * risk_config["reward_risk_min"])
    reward = max(reward_1, target_2 - entry)
    rr = reward / risk if risk > 0 else 0
    
    if rr < risk_config["reward_risk_min"]:
        return None
    
    # Quality score (0-100)
    depth_score = max(0, 100 - pullback["pullback_depth_pct"] * 2)
    vol_score = min(100, pullback["volume_ratio"] * 30)
    rr_score = min(100, rr * 25)
    quality = (depth_score * 0.3) + (vol_score * 0.4) + (rr_score * 0.3)
    
    return BullFlagSetup(
        symbol=symbol,
        timeframe=timeframe,
        impulse_start_idx=impulse["start_idx"],
        impulse_end_idx=impulse["end_idx"],
        pullback_end_idx=pullback["end_idx"],
        trigger_idx=pullback["trigger_idx"],
        impulse_low=impulse["low"],
        impulse_high=impulse["high"],
        pullback_low=pullback["pullback_low"],
        trigger_price=pullback["trigger_price"],
        impulse_pct=impulse["pct"],
        pullback_depth_pct=pullback["pullback_depth_pct"],
        volume_ratio=pullback["volume_ratio"],
        entry=round(entry, 2),
        stop=round(stop, 2),
        target_1=round(target_1, 2),
        target_2=round(target_2, 2),
        risk=risk,
        reward=reward,
        rr_ratio=rr,
        quality_score=quality,
    )


def scan_for_bullflag(
    symbol: str,
    df: pd.DataFrame,
    timeframe: str = "1Min",
) -> list[BullFlagSetup]:
    """
    Main entry point: scan a symbol's candle data for bull flag setups.
    
    Args:
        symbol: Stock ticker
        df: OHLCV DataFrame (from market_data.fetch_bars)
        timeframe: Candle timeframe string
    
    Returns:
        List of BullFlagSetup objects found
    """
    config = load_config()
    setups = []
    
    impulse_legs = detect_impulse_legs(df, config)
    
    for impulse in impulse_legs:
        pullback = detect_pullback(df, impulse, config)
        if pullback is None:
            continue
        
        setup = compute_setup(symbol, timeframe, df, impulse, pullback, config)
        if setup is not None:
            setups.append(setup)
    
    return setups
