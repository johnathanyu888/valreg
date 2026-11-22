"""Collect agent data from valorant-api.com and save the raw response.

valorant-api.com is a free, keyless, community-run API (not affiliated with Riot).
This script does not clean anything: it saves the API's answer untouched as a dated
JSON file in data/raw/. The cleaning step loads that file into SQLite later.

Run from the project folder:
    python collectors/valorant_api.py
"""

import json
from datetime import date
from pathlib import Path

import requests

URL = "https://valorant-api.com/v1/agents?isPlayableCharacter=true"

# data/raw/ relative to this file, so the script works from any working directory.
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch_agents():
    """Download the list of playable agents from valorant-api.com."""
    response = requests.get(URL, timeout=10)
    response.raise_for_status()
    return response.json()


def save_raw(data):
    """Save the untouched API response as data/raw/agents_YYYY-MM-DD.json."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"agents_{date.today().isoformat()}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    data = fetch_agents()
    path = save_raw(data)
    print(f"Saved {len(data['data'])} agents to {path}")
