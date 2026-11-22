"""Clean the newest raw agents file and load it into the SQLite database.

Reads the most recent data/raw/agents_YYYY-MM-DD.json (saved by
collectors/valorant_api.py), keeps the fields the project uses, fixes known data
problems, and rebuilds the `agents` table in data/valreg.db.

Run from the project folder:
    python cleaning/load_agents.py
"""

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "valreg.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"

# valorant-api.com uses 1970-01-01 (the Unix "zero" date) when it has no real date.
PLACEHOLDER_DATE = "1970-01-01"


def newest_raw_file():
    """Return the newest agents_*.json. ISO dates in the name sort correctly as text."""
    files = sorted(RAW_DIR.glob("agents_*.json"))
    if not files:
        raise FileNotFoundError(f"No agents_*.json in {RAW_DIR}. Run collectors/valorant_api.py first.")
    return files[-1]


def name_key(name):
    """Normalize a name for matching across sources: 'KAY/O', 'Kay/O', 'kayo' -> 'kayo'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def clean_agents(raw):
    """Turn the raw API response into a list of clean rows (tuples)."""
    rows = []
    for agent in raw["data"]:
        release_date = agent["releaseDate"][:10]  # '2020-06-02T00:00:00Z' -> '2020-06-02'
        if release_date == PLACEHOLDER_DATE:
            release_date = None
        rows.append((
            agent["uuid"],
            agent["displayName"],
            name_key(agent["displayName"]),
            agent["role"]["displayName"],
            release_date,
        ))
    return rows


def load(rows):
    """Rebuild the agents table from scratch and insert the rows."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.executemany("INSERT INTO agents VALUES (?, ?, ?, ?, ?)", rows)


if __name__ == "__main__":
    path = newest_raw_file()
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = clean_agents(raw)
    load(rows)
    missing = [r[1] for r in rows if r[4] is None]
    print(f"Loaded {len(rows)} agents from {path.name} into {DB_PATH.name}")
    print(f"{len(missing)} agents have no real release date: {', '.join(missing)}")
