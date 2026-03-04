"""
cron_runner.py — Daily automation scheduler.

Runs the full morning workflow:
  06:30 CT — Premarket scan + Discord watchlist
  08:30 CT — Start bull flag watcher
  15:00 CT — Stop watcher + send daily summary

Usage:
    python scheduler/cron_runner.py
    
    Or add to crontab:
    30 6 * * 1-5 cd /path/to/trade-ops && /path/to/venv/bin/python -m cli.main scan
"""

import os
import sys
import time
import threading
from datetime import datetime

import schedule
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()


def morning_scan():
    """Run premarket scanner and send watchlist."""
    print(f"[{datetime.now():%H:%M}] Running premarket scan...")
    try:
        from services.scanner import scan_premarket
        from services.alerts import send_watchlist
        
        df = scan_premarket()
        if not df.empty:
            candidates = df.head(15).to_dict("records")
            send_watchlist(candidates)
            print(f"  Found {len(df)} candidates, sent top {min(15, len(df))} to Discord")
            
            # Save watchlist for the watcher
            df.head(10).to_csv("data/today_watchlist.csv", index=False)
        else:
            print("  No candidates found")
    except Exception as e:
        print(f"  Error: {e}")


watcher_thread = None
watcher_running = False


def start_watcher():
    """Start the bull flag watcher in a background thread."""
    global watcher_thread, watcher_running
    
    print(f"[{datetime.now():%H:%M}] Starting bull flag watcher...")
    watcher_running = True
    
    def watch_loop():
        import pandas as pd
        from services.market_data import fetch_bars
        from services.bullflag import scan_for_bullflag
        from services.planner import build_plan
        from services.alerts import send_bullflag_alert
        from services.journal import log_signal
        
        # Load today's watchlist
        try:
            wl = pd.read_csv("data/today_watchlist.csv")
            symbols = wl["symbol"].tolist()
        except Exception:
            print("  No watchlist found. Run scan first.")
            return
        
        print(f"  Watching: {', '.join(symbols)}")
        seen = set()
        
        while watcher_running:
            for sym in symbols:
                try:
                    df = fetch_bars(sym, timeframe="1Min", limit=100)
                    if df.empty or len(df) < 10:
                        continue
                    
                    setups = scan_for_bullflag(sym, df, "1Min")
                    for setup in setups:
                        key = f"{sym}_{setup.trigger_idx}"
                        if key in seen:
                            continue
                        seen.add(key)
                        
                        plan = build_plan(setup)
                        print(f"  🐂 BULL FLAG: {sym} @ ${setup.entry:.2f}")
                        
                        log_signal(setup.to_dict(), triggered=True)
                        alert_data = {**setup.to_dict(), "shares": plan.shares, "notes": plan.notes}
                        send_bullflag_alert(alert_data)
                        
                except Exception as e:
                    pass  # Silently skip errors in background
            
            time.sleep(60)
    
    watcher_thread = threading.Thread(target=watch_loop, daemon=True)
    watcher_thread.start()


def stop_watcher():
    """Stop the watcher and send daily summary."""
    global watcher_running
    watcher_running = False
    
    print(f"[{datetime.now():%H:%M}] Stopping watcher, sending daily summary...")
    try:
        from services.journal import get_stats
        from services.alerts import send_daily_summary
        
        stats = get_stats(days=1)
        send_daily_summary(stats)
    except Exception as e:
        print(f"  Error: {e}")


def main():
    print("=" * 50)
    print("  trade-ops scheduler")
    print(f"  Started: {datetime.now():%Y-%m-%d %H:%M CT}")
    print("=" * 50)
    print()
    print("  Schedule:")
    print("    06:30 CT — Premarket scan")
    print("    08:30 CT — Bull flag watcher start")
    print("    15:00 CT — Watcher stop + summary")
    print()
    print("  Press Ctrl+C to stop")
    print()
    
    # Schedule jobs (times in local timezone)
    schedule.every().monday.at("06:30").do(morning_scan)
    schedule.every().tuesday.at("06:30").do(morning_scan)
    schedule.every().wednesday.at("06:30").do(morning_scan)
    schedule.every().thursday.at("06:30").do(morning_scan)
    schedule.every().friday.at("06:30").do(morning_scan)
    
    schedule.every().monday.at("08:30").do(start_watcher)
    schedule.every().tuesday.at("08:30").do(start_watcher)
    schedule.every().wednesday.at("08:30").do(start_watcher)
    schedule.every().thursday.at("08:30").do(start_watcher)
    schedule.every().friday.at("08:30").do(start_watcher)
    
    schedule.every().monday.at("15:00").do(stop_watcher)
    schedule.every().tuesday.at("15:00").do(stop_watcher)
    schedule.every().wednesday.at("15:00").do(stop_watcher)
    schedule.every().thursday.at("15:00").do(stop_watcher)
    schedule.every().friday.at("15:00").do(stop_watcher)
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nScheduler stopped.")


if __name__ == "__main__":
    main()
