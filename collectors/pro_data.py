"""Download the Kaggle "Valorant Champion Tour 2021-2026 Data" dataset.

Pro pick rates by agent, map, tournament and stage, scraped from vlr.gg by
Ryan Luong. MIT license. Public, so Kaggle allows downloading it without an API key.

Saves the untouched zip to data/raw/kaggle_vct/ with today's date in the name, then
extracts only the files this project uses (the full archive is ~1.3 GB unzipped,
mostly per-match player stats):
    vct_<year>/agents/*.csv   pick rates, map stats, team picks
    all_ids/*.csv             ID lookup tables

This folder is git-ignored (~160 MB). Run from the project folder:
    python collectors/pro_data.py
"""

import re
import zipfile
from datetime import date
from pathlib import Path

import requests

DATASET = "ryanluong1/valorant-champion-tour-2021-2023-data"
URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET}"

# Kaggle answers 404 to requests' default User-Agent ("python-requests/x.y"),
# so identify the script by its own name instead.
HEADERS = {"User-Agent": "valreg-collector/1.0"}

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "kaggle_vct"

# Which files inside the zip to extract.
KEEP = re.compile(r"^(vct_\d{4}/agents/|all_ids/)[^/]+\.csv$")


def download(zip_path):
    """Stream the dataset zip to disk (it is ~84 MB, so don't hold it all in memory)."""
    with requests.get(URL, headers=HEADERS, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)


def extract(zip_path):
    """Extract only the files matching KEEP. Returns how many were extracted."""
    count = 0
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if KEEP.match(name):
                z.extract(name, OUT_DIR)
                count += 1
    return count


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUT_DIR / f"vct_2021-2026_{date.today().isoformat()}.zip"
    print(f"Downloading {DATASET} ...")
    download(zip_path)
    print(f"Saved {zip_path.stat().st_size / 1e6:.0f} MB to {zip_path}")
    print(f"Extracted {extract(zip_path)} CSV files into {OUT_DIR}")
