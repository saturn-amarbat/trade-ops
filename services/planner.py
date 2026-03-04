"""
planner.py — Trade plan generator.
Computes position size, validates R:R, and builds the morning plan packet.
"""

import yaml
from dataclasses import dataclass
from services.bullflag import BullFlagSetup


@dataclass
class TradePlan:
    """A complete trade plan ready for execution."""
    symbol: str
    entry: float
    stop: float
    target_1: float
    target_2: float
    risk_per_share: float
    shares: int
    dollar_risk: float
    dollar_target: float
    rr_ratio: float
    quality_score: float
    notes: str
    
    def summary(self) -> str:
        return (
            f"{'='*40}\n"
            f"  {self.symbol} — Bull Flag Setup\n"
            f"{'='*40}\n"
            f"  Entry:    ${self.entry:.2f}\n"
            f"  Stop:     ${self.stop:.2f}\n"
            f"  Target 1: ${self.target_1:.2f} (HOD retest)\n"
            f"  Target 2: ${self.target_2:.2f} (2R)\n"
            f"{'─'*40}\n"
            f"  Shares:   {self.shares}\n"
            f"  Risk:     ${self.dollar_risk:.2f}\n"
            f"  Reward:   ${self.dollar_target:.2f}\n"
            f"  R:R:      {self.rr_ratio:.1f}:1\n"
            f"  Quality:  {self.quality_score:.0f}/100\n"
            f"{'─'*40}\n"
            f"  {self.notes}\n"
        )


def load_risk_config() -> dict:
    with open("config/settings.yaml", "r") as f:
        return yaml.safe_load(f)["risk"]


def compute_position_size(entry: float, stop: float, config: dict) -> tuple[int, float]:
    """
    Compute shares and dollar risk.
    
    Uses fixed-fractional sizing: risk no more than X% of account per trade.
    """
    risk_per_share = abs(entry - stop)
    if risk_per_share <= 0:
        return 0, 0
    
    max_dollar_risk = config["account_size"] * (config["max_risk_per_trade_pct"] / 100)
    shares = int(max_dollar_risk / risk_per_share)
    dollar_risk = shares * risk_per_share
    
    return shares, round(dollar_risk, 2)


def build_plan(setup: BullFlagSetup) -> TradePlan:
    """Convert a BullFlagSetup into an actionable TradePlan."""
    config = load_risk_config()
    shares, dollar_risk = compute_position_size(setup.entry, setup.stop, config)
    dollar_target = shares * setup.reward
    
    # Generate context notes
    notes_parts = []
    if setup.pullback_depth_pct <= 15:
        notes_parts.append("Shallow pullback (strong)")
    elif setup.pullback_depth_pct <= 25:
        notes_parts.append("Normal pullback depth")
    
    if setup.volume_ratio >= 3:
        notes_parts.append("Excellent volume dry-up")
    elif setup.volume_ratio >= 1.5:
        notes_parts.append("Good volume dry-up")
    
    notes = " | ".join(notes_parts) if notes_parts else "Standard setup"
    
    return TradePlan(
        symbol=setup.symbol,
        entry=setup.entry,
        stop=setup.stop,
        target_1=setup.target_1,
        target_2=setup.target_2,
        risk_per_share=setup.risk,
        shares=shares,
        dollar_risk=dollar_risk,
        dollar_target=round(dollar_target, 2),
        rr_ratio=setup.rr_ratio,
        quality_score=setup.quality_score,
        notes=notes,
    )
