"""
alerts.py — Discord webhook alert service.
Sends rich embed notifications for:
  - Morning watchlist (premarket scan results)
  - Bull flag triggers (real-time during market)
  - Daily summary
"""

import os
import json
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()


WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")


def send_watchlist(candidates: list[dict]) -> bool:
    """
    Send the morning premarket watchlist to Discord.
    
    Args:
        candidates: List of dicts with symbol, price, gap_pct, rvol, score
    """
    if not WEBHOOK_URL or not candidates:
        return False
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M CT")
    
    # Build table
    lines = ["```"]
    lines.append(f"{'Sym':<6} {'Price':>7} {'Gap%':>6} {'RVOL':>5} {'Score':>6}")
    lines.append("─" * 36)
    for c in candidates[:15]:  # Top 15
        lines.append(
            f"{c['symbol']:<6} ${c['price']:>6.2f} {c['gap_pct']:>5.1f}% "
            f"{c.get('rvol', 0):>4.1f}x {c.get('score', 0):>5.1f}"
        )
    lines.append("```")
    
    # TradingView links for top 5
    tv_links = []
    for c in candidates[:5]:
        tv_links.append(
            f"[{c['symbol']}](https://www.tradingview.com/chart/?symbol={c['symbol']})"
        )
    
    embed = {
        "title": f"🔍 Premarket Watchlist — {now}",
        "description": "\n".join(lines),
        "color": 3066993,  # Green
        "fields": [
            {
                "name": "📊 Quick Charts (TradingView)",
                "value": " | ".join(tv_links) if tv_links else "None",
            }
        ],
        "footer": {"text": "trade-ops | Not financial advice"},
    }
    
    payload = {"embeds": [embed]}
    
    try:
        resp = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"Discord alert error: {e}")
        return False


def send_bullflag_alert(plan_dict: dict) -> bool:
    """
    Send a bull flag trigger alert to Discord.
    
    Args:
        plan_dict: TradePlan as dict (from plan.summary() or similar)
    """
    if not WEBHOOK_URL:
        return False
    
    sym = plan_dict["symbol"]
    tv_link = f"https://www.tradingview.com/chart/?symbol={sym}"
    
    embed = {
        "title": f"🐂 BULL FLAG — {sym}",
        "color": 15844367,  # Gold
        "fields": [
            {"name": "Entry", "value": f"${plan_dict['entry']:.2f}", "inline": True},
            {"name": "Stop", "value": f"${plan_dict['stop']:.2f}", "inline": True},
            {"name": "Target", "value": f"${plan_dict['target_1']:.2f}", "inline": True},
            {"name": "R:R", "value": f"{plan_dict['rr_ratio']:.1f}:1", "inline": True},
            {"name": "Shares", "value": str(plan_dict.get("shares", "—")), "inline": True},
            {"name": "Quality", "value": f"{plan_dict['quality_score']:.0f}/100", "inline": True},
            {"name": "Chart", "value": f"[Open TradingView]({tv_link})"},
        ],
        "footer": {"text": f"trade-ops | {plan_dict.get('notes', '')}"},
    }
    
    payload = {
        "content": "@everyone 🚨 Bull flag triggered!" if plan_dict.get("quality_score", 0) >= 70 else "",
        "embeds": [embed],
    }
    
    try:
        resp = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"Discord alert error: {e}")
        return False


def send_daily_summary(stats: dict) -> bool:
    """Send end-of-day summary."""
    if not WEBHOOK_URL:
        return False
    
    embed = {
        "title": "📋 Daily Summary",
        "color": 10181046,  # Purple
        "fields": [
            {"name": "Signals", "value": str(stats.get("total_signals", 0)), "inline": True},
            {"name": "Triggered", "value": str(stats.get("triggered", 0)), "inline": True},
            {"name": "Hit Target", "value": str(stats.get("hit_target", 0)), "inline": True},
            {"name": "Stopped Out", "value": str(stats.get("stopped_out", 0)), "inline": True},
        ],
        "footer": {"text": "trade-ops | Review your journal"},
    }
    
    payload = {"embeds": [embed]}
    
    try:
        resp = requests.post(WEBHOOK_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"Discord alert error: {e}")
        return False
