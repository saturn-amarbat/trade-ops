"""
journal.py — SQLite-based trade signal journal.
Logs every detected setup, whether it triggered, and the outcome.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path


DB_PATH = Path("data/journal.db")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            setup_type TEXT DEFAULT 'bull_flag',
            entry REAL,
            stop REAL,
            target_1 REAL,
            target_2 REAL,
            rr_ratio REAL,
            quality_score REAL,
            triggered INTEGER DEFAULT 0,
            outcome TEXT,
            pnl REAL,
            notes TEXT,
            raw_data TEXT
        )
    """)
    conn.commit()
    return conn


def log_signal(setup_dict: dict, triggered: bool = False, notes: str = "") -> int:
    """Log a detected signal to the journal. Returns the signal ID."""
    conn = _get_conn()
    cursor = conn.execute(
        """INSERT INTO signals 
           (timestamp, symbol, entry, stop, target_1, target_2, rr_ratio, 
            quality_score, triggered, notes, raw_data)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(),
            setup_dict.get("symbol", ""),
            setup_dict.get("entry"),
            setup_dict.get("stop"),
            setup_dict.get("target_1"),
            setup_dict.get("target_2"),
            setup_dict.get("rr_ratio"),
            setup_dict.get("quality_score"),
            int(triggered),
            notes,
            json.dumps(setup_dict),
        ),
    )
    conn.commit()
    signal_id = cursor.lastrowid
    conn.close()
    return signal_id


def update_outcome(signal_id: int, outcome: str, pnl: float = 0) -> None:
    """Update a signal with its outcome after the trade."""
    conn = _get_conn()
    conn.execute(
        "UPDATE signals SET outcome = ?, pnl = ? WHERE id = ?",
        (outcome, pnl, signal_id),
    )
    conn.commit()
    conn.close()


def get_today_signals() -> list[dict]:
    """Get all signals from today."""
    conn = _get_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor = conn.execute(
        "SELECT * FROM signals WHERE timestamp LIKE ?",
        (f"{today}%",),
    )
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_stats(days: int = 30) -> dict:
    """Get aggregate stats for the last N days."""
    conn = _get_conn()
    cursor = conn.execute(
        """SELECT 
               COUNT(*) as total_signals,
               SUM(CASE WHEN triggered = 1 THEN 1 ELSE 0 END) as triggered,
               SUM(CASE WHEN outcome = 'target' THEN 1 ELSE 0 END) as hit_target,
               SUM(CASE WHEN outcome = 'stopped' THEN 1 ELSE 0 END) as stopped_out,
               SUM(COALESCE(pnl, 0)) as total_pnl
           FROM signals
           WHERE timestamp >= date('now', ?)""",
        (f"-{days} days",),
    )
    row = cursor.fetchone()
    conn.close()
    
    return {
        "total_signals": row[0] or 0,
        "triggered": row[1] or 0,
        "hit_target": row[2] or 0,
        "stopped_out": row[3] or 0,
        "total_pnl": row[4] or 0,
    }
