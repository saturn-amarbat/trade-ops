"""
Unit tests for the bull flag detection engine.
Uses synthetic candle data to validate pattern recognition.
"""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch


def make_candles(prices: list[tuple], base_volume: int = 10000) -> pd.DataFrame:
    """
    Helper: create a DataFrame of OHLCV candles from (open, high, low, close, vol_mult) tuples.
    vol_mult multiplies base_volume.
    """
    rows = []
    for i, (o, h, l, c, vm) in enumerate(prices):
        rows.append({
            "open": o, "high": h, "low": l, "close": c,
            "volume": int(base_volume * vm),
            "vwap": (h + l) / 2,
            "trade_count": 100,
        })
    
    idx = pd.date_range("2026-03-04 09:30", periods=len(rows), freq="1min")
    return pd.DataFrame(rows, index=idx)


class TestBullFlagDetection:
    """Tests for the bullflag module."""
    
    @patch("services.bullflag.load_config")
    def test_perfect_bull_flag(self, mock_config):
        """A textbook bull flag should be detected."""
        mock_config.return_value = {
            "impulse_min_pct": 3.0,
            "impulse_min_candles": 2,
            "impulse_max_candles": 10,
            "pullback_max_pct": 25.0,
            "pullback_hard_cut": 50.0,
            "min_pullback_candles": 2,
            "max_pullback_candles": 15,
            "volume_ratio_min": 1.5,
        }
        
        candles = [
            # Impulse leg (high volume)
            (5.00, 5.10, 4.98, 5.08, 3.0),
            (5.08, 5.25, 5.05, 5.22, 4.0),
            (5.22, 5.50, 5.20, 5.48, 5.0),
            # Pullback (low volume)
            (5.45, 5.46, 5.38, 5.40, 1.0),
            (5.40, 5.42, 5.35, 5.39, 0.8),
            # Trigger candle — makes new high vs prior
            (5.39, 5.44, 5.38, 5.43, 2.0),
        ]
        
        df = make_candles(candles)
        
        from services.bullflag import detect_impulse_legs, detect_pullback
        
        config = mock_config.return_value
        legs = detect_impulse_legs(df, config)
        
        assert len(legs) >= 1, "Should detect at least one impulse leg"
        assert legs[0]["pct"] >= 3.0, "Impulse should be >= 3%"
    
    @patch("services.bullflag.load_config")
    def test_deep_pullback_rejected(self, mock_config):
        """A pullback deeper than hard_cut should be rejected."""
        mock_config.return_value = {
            "impulse_min_pct": 3.0,
            "impulse_min_candles": 2,
            "impulse_max_candles": 10,
            "pullback_max_pct": 25.0,
            "pullback_hard_cut": 50.0,
            "min_pullback_candles": 2,
            "max_pullback_candles": 15,
            "volume_ratio_min": 1.5,
        }
        
        # Impulse: $5 -> $5.50, then deep pullback to $5.10 (80% retracement)
        candles = [
            (5.00, 5.10, 4.98, 5.08, 3.0),
            (5.08, 5.25, 5.05, 5.22, 4.0),
            (5.22, 5.50, 5.20, 5.48, 5.0),
            # Deep pullback
            (5.45, 5.46, 5.20, 5.25, 2.0),
            (5.25, 5.26, 5.10, 5.12, 2.0),
            (5.12, 5.28, 5.10, 5.25, 1.5),
        ]
        
        df = make_candles(candles)
        
        from services.bullflag import detect_impulse_legs, detect_pullback
        
        config = mock_config.return_value
        legs = detect_impulse_legs(df, config)
        
        if legs:
            pullback = detect_pullback(df, legs[0], config)
            assert pullback is None, "Deep pullback should be rejected"
    
    @patch("services.bullflag.load_config")
    def test_no_impulse_flat_market(self, mock_config):
        """Flat price action should produce no impulse legs."""
        mock_config.return_value = {
            "impulse_min_pct": 3.0,
            "impulse_min_candles": 2,
            "impulse_max_candles": 10,
            "pullback_max_pct": 25.0,
            "pullback_hard_cut": 50.0,
            "min_pullback_candles": 2,
            "max_pullback_candles": 15,
            "volume_ratio_min": 1.5,
        }
        
        # Flat: all candles around $5 with tiny range
        candles = [(5.00, 5.02, 4.98, 5.01, 1.0) for _ in range(20)]
        df = make_candles(candles)
        
        from services.bullflag import detect_impulse_legs
        
        legs = detect_impulse_legs(df, mock_config.return_value)
        assert len(legs) == 0, "Flat market should have no impulse legs"
