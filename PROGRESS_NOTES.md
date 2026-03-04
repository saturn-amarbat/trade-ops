# trade-ops — Progress Notes & Next Steps

## Original goal
Build a free-first, automation-friendly day trading workflow tool (Ross Cameron / Warrior Trading-inspired) that:
- Scans US stocks premarket for “stocks in play” (gappers + high relative volume + small-cap price range).
- Detects **bull flag** setups on intraday candles (rule-based, transcript-aligned).
- Produces a concrete trade plan (entry/stop/targets, 2:1 minimum R:R).
- Sends alerts to phone (Discord) + logs everything for review.
- Is also a strong CS portfolio project (real-time-ish data pipeline, automation, testing, stats).

## What’s done already (current repo state)
Repo: https://github.com/saturn-amarbat/trade-ops

### Core workflow
- CLI commands implemented:
  - `python -m cli.main scan` (premarket scanner)
  - `python -m cli.main watch` (bull flag watcher)
  - `python -m cli.main journal` (today’s signals)
  - `python -m cli.main stats` (aggregate stats)
- Daily scheduler implemented (`scheduler/cron_runner.py`) to run scan + start watcher + stop + summary.

### Data + strategy implementation
- Alpaca integration exists:
  - Pulls snapshots and bars (REST) and includes websocket stub.
- Premarket scanner (`services/scanner.py`):
  - Filters by price, gap %, minimum volume.
  - Computes RVOL using 20-day daily volume average.
- Bull flag detector (`services/bullflag.py`):
  - Impulse → pullback → trigger logic.
  - Pullback depth filters (soft max 25%, hard cut 50%).
  - Volume dry-up filter (impulse avg vol / pullback avg vol).
  - Trade plan fields: entry, stop, target_1 (HOD retest), target_2 (2R), quality score.
- Trade planner (`services/planner.py`):
  - 1% risk sizing default, 2:1 minimum R:R enforcement.
- Alerts (`services/alerts.py`):
  - Discord watchlist embed.
  - Discord bull-flag trigger embed (with TradingView link).
  - Daily summary.
- Journal (`services/journal.py`):
  - SQLite storage of detected signals + basic stats.

### Tests
- Basic unit tests exist for bull flag and scanner filters (`tests/`).

## What needs to be tested (before trusting with real money)

### 1) End-to-end “happy path” tests (manual + scripted)
- Confirm `.env` secrets load correctly (Alpaca keys + Discord webhook).
- Confirm `scan` produces at least a few candidates on normal market days.
- Confirm Discord watchlist embed renders (table formatting + links).
- Confirm `watch` runs without crashing for 30–60 minutes.
- Confirm a detected setup actually triggers once (you’ll likely need to test on historical day replay or pick a volatile day).

### 2) Data correctness tests
- Validate gap% calculation uses consistent reference (prev close vs current trade).
- Validate RVOL is computed correctly and isn’t skewed by premarket volume vs regular session.
- Validate bars timestamps and timezone handling (America/Chicago vs market ET).

### 3) Strategy validity tests (statistical)
- Build a backtest harness (see “Needs to be added”).
- Measure:
  - Win rate to 1R and 2R.
  - Expectancy (avg R).
  - Avg slippage assumptions.
  - Breakdown by time of day (open vs midday).
- Paper trade for 2–4 weeks and compare:
  - Bot signals vs what you would actually trade.
  - Execution quality on Robinhood vs “ideal fill”.

### 4) Reliability tests
- Rate-limit resilience (Alpaca API call errors, retry/backoff).
- Graceful behavior on empty data (halts, missing snapshots, thin tickers).
- Logging: ensure exceptions are captured, not silently swallowed.

## What needs to be added / improved (robust + financially useful)

### Highest ROI additions (do these first)

#### A) Backtest + replay engine (critical)
Goal: prove the bull flag detector has positive expectancy *before* increasing size.
- Create `backtest/` module:
  - Download historical 1-min bars for a list of symbols/days.
  - Run bullflag detection candle-by-candle (no lookahead bias).
  - Simulate entry (break of prior high), stop (pullback low), targets (1R/2R/HOD).
  - Output CSV summary + metrics (win rate, avg R, max drawdown by day).

#### B) “Stocks in play” feed improvements
Current scanner pulls from a huge asset list; it’s slow and noisy.
- Add a seed list stage using Alpaca “most active”/gainers endpoint (or a free gappers source) instead of scanning all assets.
- Add filters:
  - Spread estimate (from quotes) max threshold.
  - Min $ volume (price * volume).
  - Halt detection / avoid frequent halters.

#### C) Real-time streaming watcher
Current watcher polls every 60 seconds; this can miss triggers.
- Use Alpaca websocket bars/quotes.
- Maintain in-memory rolling candle window (last 100 bars) per symbol.
- Trigger alerts immediately when breakout conditions occur.

#### D) Add “float” and “news catalyst” inputs
Ross heavily weights float and news.
- Float:
  - Add an optional float data provider (may require a free API key).
  - Cache floats in SQLite.
- News catalyst:
  - Add a “has news?” boolean from a news API or RSS.
  - If not available free, at least add manual input field in config to mark catalysts.

### Reliability / engineering upgrades
- Config overhaul:
  - Separate `config/settings.yaml` into `universe.yaml`, `strategy.yaml`, `risk.yaml`.
- Logging:
  - Add structured logging (JSON) and rotating file logs.
- Error handling:
  - Retry with exponential backoff on Alpaca failures.
  - Circuit breaker if API is down.
- Deterministic tests:
  - Replace synthetic-only tests with a small “golden dataset” of candles stored as CSV in `tests/fixtures/`.

### Trading practicality upgrades
- Add “entry type” options:
  - Break of prior candle high.
  - Break of pullback trendline.
  - Break of HOD.
- Add “no-trade conditions”:
  - Pullback too choppy.
  - Volume pattern wrong (selling heavier than buying).
  - Too close to major resistance.
- Add partials logic:
  - Take 1/2 off at 1R, move stop to break-even.

## Inputs you still need to provide / set up

### Required to run
- Alpaca API keys (paper is fine).
- Discord webhook URL.

### Strongly recommended
- Your account size and max risk per trade in `config/settings.yaml`.
- Your preferred trading time window (e.g., only 8:30–10:30 CT).
- Your max spread and min volume constraints (to avoid trash tickers).

### Optional (future)
- Float data API key (if using).
- News API key (if using).

## Definition of “done” (financial usefulness)
This project is “financially usable” when:
- Backtest shows positive expectancy after fees/slippage assumptions.
- Paper trading results match backtest within reason.
- Live watcher is websocket-based (no missed triggers).
- Alerts are low-noise (≤10/day) and high-quality.
- Journal can compute R-multiples and produce weekly stats.

## Suggested Claude Code tasks (copy/paste)

1) Implement backtest engine with no lookahead bias, output CSV metrics + summary.
2) Replace full-asset scan with a tighter “stocks in play” seeding method.
3) Convert watcher to Alpaca websocket streaming.
4) Add robust logging + retry/backoff.
5) Add fixtures + tests for at least 3 real historical bull-flag examples.
