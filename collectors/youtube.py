"""Collect YouTube interest data for every agent and competitive map.

Uses the YouTube Data API v3 (free, needs an API key in .env as YOUTUBE_API_KEY).
For each agent and map it searches "Valorant <name> guide" for videos uploaded in
the last WINDOW_DAYS days, then looks up those videos' view counts. The untouched
answers are saved to data/raw/youtube_YYYY-MM-DD.json. Views per day, medians and
so on are computed later in cleaning/analysis, not here.

Quota (checked in Google's docs on 2026-11-22): search.list is limited to 100 calls
per day per project; videos.list draws on a separate 10,000-unit daily pool at 1 unit
per call. Quotas reset at midnight Pacific Time. One run uses about 43 searches
(30 agents + 13 maps), so run it at most twice a day.

Run from the project folder:
    python collectors/youtube.py
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

API_URL = "https://www.googleapis.com/youtube/v3"
WINDOW_DAYS = 90   # only videos uploaded in the last 90 days
MAX_RESULTS = 25   # videos per search (max 50; costs the same either way)

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
ENV_PATH = ROOT / ".env"


def load_api_key():
    """Read YOUTUBE_API_KEY from the environment or from the git-ignored .env file."""
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key and ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "YOUTUBE_API_KEY":
                key = value.strip().strip('"')
    if not key:
        sys.exit(
            "No YOUTUBE_API_KEY found. Create a key in Google Cloud Console "
            "(APIs & Services > enable 'YouTube Data API v3' > Credentials > API key), "
            "then add a line YOUTUBE_API_KEY=your-key to .env in the project folder."
        )
    return key


def newest_raw(prefix):
    """Load the newest data/raw/<prefix>_YYYY-MM-DD.json saved by collectors/valorant_api.py."""
    files = sorted(RAW_DIR.glob(f"{prefix}_*.json"))
    if not files:
        sys.exit(f"No {prefix}_*.json in {RAW_DIR}. Run collectors/valorant_api.py first.")
    return json.loads(files[-1].read_text(encoding="utf-8"))["data"]


def topics():
    """List of (type, name) to search for: all agents, plus maps that have bomb sites.

    Maps without a tactical description (Skirmish, The Range, deathmatch maps) are not
    competitive, so they are skipped here to save search quota.
    """
    agents = [("agent", a["displayName"]) for a in newest_raw("agents")]
    maps = sorted({m["displayName"] for m in newest_raw("maps") if m.get("tacticalDescription")})
    return agents + [("map", name) for name in maps]


def api_get(endpoint, key, **params):
    """Call one YouTube Data API endpoint and return its JSON."""
    response = requests.get(f"{API_URL}/{endpoint}", params={**params, "key": key}, timeout=15)
    response.raise_for_status()
    return response.json()


def collect_topic(name, key, published_after):
    """Search for one topic, then fetch statistics for the videos found."""
    query = f"Valorant {name} guide"  # "Valorant" avoids ambiguous names like Sage or Viper
    search = api_get(
        "search", key,
        part="snippet", type="video", q=query, order="relevance",
        publishedAfter=published_after, maxResults=MAX_RESULTS,
    )
    ids = [item["id"]["videoId"] for item in search.get("items", [])]
    videos = api_get("videos", key, part="snippet,statistics", id=",".join(ids)) if ids else {"items": []}
    return {"query": query, "search": search, "videos": videos}


def save_raw(data):
    """Save the run as data/raw/youtube_YYYY-MM-DD.json."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"youtube_{date.today().isoformat()}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


if __name__ == "__main__":
    key = load_api_key()
    now = datetime.now(timezone.utc)
    published_after = (now - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run = {
        "collected_at": now.isoformat(),
        "window_days": WINDOW_DAYS,
        "max_results": MAX_RESULTS,
        "results": [],
    }
    todo = topics()
    try:
        for i, (kind, name) in enumerate(todo, start=1):
            result = collect_topic(name, key, published_after)
            run["results"].append({"type": kind, "name": name, **result})
            print(f"[{i}/{len(todo)}] {name}: {len(result['videos']['items'])} videos")
    except requests.HTTPError as error:
        # Most likely the daily quota ran out (HTTP 403). Keep what we already have.
        print(f"Stopped early: {error}")
    path = save_raw(run)
    print(f"Saved {len(run['results'])} of {len(todo)} topics to {path}")
