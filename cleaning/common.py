"""Helpers shared by every cleaning script, so each rule lives in exactly one place."""

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "valreg.db"
SCHEMA_DIR = ROOT / "db" / "schema"


def name_key(name):
    """Normalize a name for matching across sources: 'KAY/O', 'Kay/O', 'kayo' -> 'kayo'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def newest_raw(prefix):
    """Load the newest data/raw/<prefix>_YYYY-MM-DD.json. Returns (path, data).

    ISO dates in the file name sort correctly as text, so the last file is the newest.
    """
    files = sorted(RAW_DIR.glob(f"{prefix}_*.json"))
    if not files:
        raise FileNotFoundError(f"No {prefix}_*.json in {RAW_DIR}. Run collectors/valorant_api.py first.")
    return files[-1], json.loads(files[-1].read_text(encoding="utf-8"))


def connect():
    """Open the project database."""
    return sqlite3.connect(DB_PATH)


def rebuild_tables(conn, schema_name):
    """Drop and recreate only the tables defined in db/schema/<schema_name>.sql."""
    conn.executescript((SCHEMA_DIR / f"{schema_name}.sql").read_text(encoding="utf-8"))
