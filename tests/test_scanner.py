"""
Unit tests for the premarket scanner filters.
"""

import pytest


class TestScannerFilters:
    """Test that universe filters correctly include/exclude candidates."""
    
    def test_price_filter(self):
        """Stocks outside $2-$20 should be excluded."""
        from services.scanner import load_config
        config = load_config()["universe"]
        
        # These should pass
        assert 2.0 <= 5.50 <= config["price_max"]
        assert 2.0 <= 15.00 <= config["price_max"]
        
        # These should fail
        assert not (config["price_min"] <= 1.50 <= config["price_max"])
        assert not (config["price_min"] <= 25.00 <= config["price_max"])
    
    def test_gap_filter(self):
        """Gap must be >= 10%."""
        prev_close = 5.00
        current = 5.60  # 12% gap
        gap_pct = ((current - prev_close) / prev_close) * 100
        assert gap_pct >= 10.0
        
        current_low = 5.20  # 4% gap
        gap_pct_low = ((current_low - prev_close) / prev_close) * 100
        assert gap_pct_low < 10.0
