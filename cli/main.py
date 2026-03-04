"""
CLI entry point for trade-ops.

Usage:
    python -m cli.main scan          # Run premarket scanner
    python -m cli.main watch         # Start live bull flag watcher
    python -m cli.main journal       # Show today's signals
    python -m cli.main stats         # Show 30-day stats
"""

import click
from tabulate import tabulate


@click.group()
def cli():
    """trade-ops — Automated day trading workflow tools."""
    pass


@cli.command()
@click.option("--top", default=10, help="Number of top candidates to show")
def scan(top: int):
    """Run the premarket gapper scanner."""
    click.echo("🔍 Running premarket scanner...")
    
    from services.scanner import scan_premarket
    from services.alerts import send_watchlist
    
    df = scan_premarket()
    
    if df.empty:
        click.echo("No candidates found matching criteria.")
        return
    
    df_show = df.head(top)
    click.echo(f"\n📊 Top {len(df_show)} Premarket Gappers:\n")
    click.echo(tabulate(
        df_show[["symbol", "price", "gap_pct", "rvol", "score"]].values,
        headers=["Symbol", "Price", "Gap%", "RVOL", "Score"],
        tablefmt="simple",
        floatfmt=".1f",
    ))
    
    # Send to Discord
    candidates = df_show.to_dict("records")
    if send_watchlist(candidates):
        click.echo("\n✅ Watchlist sent to Discord")
    else:
        click.echo("\n⚠️  Discord alert skipped (check webhook config)")


@cli.command()
@click.option("--symbols", default="", help="Comma-separated symbols to watch (default: from scanner)")
@click.option("--timeframe", default="1Min", help="Candle timeframe: 1Min or 5Min")
def watch(symbols: str, timeframe: str):
    """Start live bull flag watcher after market open."""
    import time
    from datetime import datetime
    
    from services.market_data import fetch_bars
    from services.bullflag import scan_for_bullflag
    from services.planner import build_plan
    from services.alerts import send_bullflag_alert
    from services.journal import log_signal
    
    if symbols:
        watch_list = [s.strip().upper() for s in symbols.split(",")]
    else:
        click.echo("🔍 Running scanner first to get watch list...")
        from services.scanner import scan_premarket
        df = scan_premarket()
        if df.empty:
            click.echo("No candidates. Provide --symbols manually.")
            return
        watch_list = df["symbol"].head(10).tolist()
    
    click.echo(f"\n👁️  Watching {len(watch_list)} symbols: {', '.join(watch_list)}")
    click.echo(f"   Timeframe: {timeframe}")
    click.echo(f"   Scanning every 60 seconds... (Ctrl+C to stop)\n")
    
    seen_triggers = set()
    
    try:
        while True:
            for sym in watch_list:
                try:
                    df = fetch_bars(sym, timeframe=timeframe, limit=100)
                    if df.empty or len(df) < 10:
                        continue
                    
                    setups = scan_for_bullflag(sym, df, timeframe)
                    
                    for setup in setups:
                        key = f"{sym}_{setup.trigger_idx}"
                        if key in seen_triggers:
                            continue
                        seen_triggers.add(key)
                        
                        plan = build_plan(setup)
                        click.echo(plan.summary())
                        
                        # Log to journal
                        log_signal(setup.to_dict(), triggered=True)
                        
                        # Alert to Discord
                        alert_data = {**setup.to_dict(), "shares": plan.shares, "notes": plan.notes}
                        send_bullflag_alert(alert_data)
                        
                except Exception as e:
                    click.echo(f"  ⚠️ Error scanning {sym}: {e}")
            
            time.sleep(60)
    
    except KeyboardInterrupt:
        click.echo("\n🛑 Watcher stopped.")


@cli.command()
def journal():
    """Show today's detected signals."""
    from services.journal import get_today_signals
    
    signals = get_today_signals()
    if not signals:
        click.echo("No signals today.")
        return
    
    click.echo(f"\n📓 Today's Signals ({len(signals)}):\n")
    for s in signals:
        status = "✅ Triggered" if s["triggered"] else "👁️ Detected"
        outcome = s.get("outcome", "pending") or "pending"
        click.echo(
            f"  {s['symbol']:6s} | {status} | "
            f"Entry ${s['entry']:.2f} | Stop ${s['stop']:.2f} | "
            f"R:R {s['rr_ratio']:.1f}:1 | Q:{s['quality_score']:.0f} | {outcome}"
        )


@cli.command()
@click.option("--days", default=30, help="Number of days to show stats for")
def stats(days: int):
    """Show aggregate signal stats."""
    from services.journal import get_stats
    
    s = get_stats(days)
    click.echo(f"\n📊 Stats (last {days} days):\n")
    click.echo(f"  Total signals:  {s['total_signals']}")
    click.echo(f"  Triggered:      {s['triggered']}")
    click.echo(f"  Hit target:     {s['hit_target']}")
    click.echo(f"  Stopped out:    {s['stopped_out']}")
    click.echo(f"  Total P&L:      ${s['total_pnl']:.2f}")


if __name__ == "__main__":
    cli()
