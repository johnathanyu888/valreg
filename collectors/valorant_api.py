"""Collect agent and map data from valorant-api.com and save the raw responses.

valorant-api.com is a free, keyless, community-run API (not affiliated with Riot).
This script does not clean anything: it saves each answer untouched as a dated
JSON file in data/raw/ (agents_YYYY-MM-DD.json, maps_YYYY-MM-DD.json).
Filtering (for example, the maps list includes non-competitive maps such as
Skirmish and The Range) happens later in the cleaning step.

Run from the project folder:
    python collectors/valorant_api.py
"""

import json
from datetime import date
from pathlib import Path

import requests

BASE_URL = "https://valorant-api.com/v1"

# Each entry: name used in the file name -> API path.
# isPlayableCharacter=true removes a duplicate, non-playable copy of one agent.
ENDPOINTS = {
    "agents": "/agents?isPlayableCharacter=true",
    "maps": "/maps",
}

# data/raw/ relative to this file, so the script works from any working directory.
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def fetch(path):
    """Download one endpoint from valorant-api.com and return its JSON."""
    response = requests.get(BASE_URL + path, timeout=10)
    response.raise_for_status()
    return response.json()


def save_raw(name, data):
    """Save an untouched API response as data/raw/<name>_YYYY-MM-DD.json."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{name}_{date.today().isoformat()}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    for name, path in ENDPOINTS.items():
        data = fetch(path)
        saved = save_raw(name, data)
        print(f"Saved {len(data['data'])} {name} to {saved}")
