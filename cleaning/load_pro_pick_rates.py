"""Clean the Kaggle pro pick rates and load them into `events` and `pro_pick_rates`.

Source: data/raw/kaggle_vct/vct_<year>/agents/ (saved by collectors/pro_data.py).
Must run after load_agents.py and load_maps.py, because rows are joined to their UUIDs.

What the cleaning does:
  - Keeps only whole-event rows ('All Stages' + 'All Match Types'). The source also has
    a row for every stage and playoff round; mixing them would count picks twice.
  - Identifies an event by year + name, because some names repeat across years.
  - Turns '62%' into 62.0 and checks every value is between 0 and 100.
  - Matches agent and map names to UUIDs via name_key ('kayo' -> KAY/O), and stops
    with an error if any name doesn't match, so nothing is silently dropped.
  - Adds maps_played (sample size) from maps_stats.csv.
  - Adds each event's season phase (its order within the year) and start/end dates from
    the hand-made data/raw/manual/event_dates.csv (the Kaggle data has no dates).
    Blank dates stay NULL.

Run from the project folder:
    python cleaning/load_pro_pick_rates.py
"""

import pandas as pd

from common import RAW_DIR, connect, name_key, rebuild_tables

KAGGLE_DIR = RAW_DIR / "kaggle_vct"
DATES_PATH = RAW_DIR / "manual" / "event_dates.csv"
ALL_MAPS = "All Maps"


def add_dates(events):
    """Join hand-entered phase and start/end dates onto events, after checking the file is sane."""
    dates = pd.read_csv(DATES_PATH, dtype=str).fillna("")
    dates["year"] = dates["year"].astype(int)

    phase = pd.to_numeric(dates["phase"], errors="coerce")
    if phase.isna().any() or (phase < 1).any() or (phase % 1 != 0).any():
        raise ValueError(f"phase must be a whole number from 1 up for:\n{dates.loc[phase.isna() | (phase < 1), 'name']}")
    dates["phase"] = phase.astype(int)

    unknown = dates.merge(events, on=["year", "name"], how="left", indicator=True)
    unknown = unknown[unknown["_merge"] == "left_only"]
    if len(unknown):
        raise ValueError(f"event_dates.csv has events not in the Kaggle data:\n{unknown[['year', 'name']]}")

    filled = dates[(dates["start_date"] != "") | (dates["end_date"] != "")]
    for col in ("start_date", "end_date"):
        parsed = pd.to_datetime(filled[col], format="%Y-%m-%d", errors="coerce")
        if parsed.isna().any():
            raise ValueError(f"Bad or missing {col} (need YYYY-MM-DD) for:\n{filled.loc[parsed.isna(), 'name']}")
    backwards = filled[filled["end_date"] < filled["start_date"]]  # ISO dates compare correctly as text
    if len(backwards):
        raise ValueError(f"end_date before start_date for:\n{backwards['name']}")

    events = events.merge(dates[["year", "name", "phase"]], on=["year", "name"], how="left")
    events["phase"] = events["phase"].astype("Int64")  # whole numbers that can also be empty
    return events.merge(filled[["year", "name", "start_date", "end_date"]], on=["year", "name"], how="left")


def read_years(file_name):
    """Read vct_<year>/agents/<file_name> for every year into one table with a year column."""
    frames = []
    for path in sorted(KAGGLE_DIR.glob(f"vct_*/agents/{file_name}")):
        year = int(path.parts[-3].removeprefix("vct_"))
        frames.append(pd.read_csv(path).assign(year=year))
    if not frames:
        raise FileNotFoundError(f"No {file_name} under {KAGGLE_DIR}. Run collectors/pro_data.py first.")
    return pd.concat(frames, ignore_index=True)


def whole_event(df):
    """Keep only the rows that summarize an entire event."""
    return df[(df["Stage"] == "All Stages") & (df["Match Type"] == "All Match Types")]


def to_uuid(names, lookup, what):
    """Map source names to UUIDs via name_key. Raise if any name has no match."""
    keys = names.map(name_key)
    unmatched = sorted(set(names[~keys.isin(lookup.keys())]))
    if unmatched:
        raise ValueError(f"{what} names with no match in the database: {unmatched}")
    return keys.map(lookup)


def clean(conn):
    """Return (events, pick_rates) as clean DataFrames ready to insert."""
    picks = whole_event(read_years("agents_pick_rates.csv"))
    stats = whole_event(read_years("maps_stats.csv"))

    # Pick rate: '62%' -> 62.0, then check the range.
    picks = picks.assign(pick_rate=picks["Pick Rate"].str.rstrip("%").astype(float))
    bad = picks[~picks["pick_rate"].between(0, 100)]
    if len(bad):
        raise ValueError(f"{len(bad)} pick rates outside 0-100:\n{bad.head()}")

    # Events: one row per (year, name), numbered in a stable order.
    events = (picks[["year", "Tournament"]].drop_duplicates()
              .sort_values(["year", "Tournament"]).reset_index(drop=True)
              .rename(columns={"Tournament": "name"}))
    events.insert(0, "event_id", range(1, len(events) + 1))
    picks = picks.merge(events, left_on=["year", "Tournament"], right_on=["year", "name"])
    events = add_dates(events)

    # Sample size: maps played at that event, on that map (or all maps).
    stats = stats.rename(columns={"Total Maps Played": "maps_played"})
    if stats.duplicated(["year", "Tournament", "Map"]).any():
        raise ValueError("maps_stats.csv has more than one row for the same event and map")
    picks = picks.merge(stats[["year", "Tournament", "Map", "maps_played"]],
                        on=["year", "Tournament", "Map"], how="left")

    # Names -> UUIDs.
    agents = dict(conn.execute("SELECT name_key, uuid FROM agents"))
    maps = dict(conn.execute("SELECT name_key, uuid FROM maps"))
    picks["agent_uuid"] = to_uuid(picks["Agent"], agents, "Agent")
    per_map = picks["Map"] != ALL_MAPS
    picks["map_uuid"] = None
    picks.loc[per_map, "map_uuid"] = to_uuid(picks.loc[per_map, "Map"], maps, "Map")

    pick_rates = picks[["event_id", "map_uuid", "agent_uuid", "pick_rate", "maps_played"]]
    if pick_rates.duplicated(["event_id", "map_uuid", "agent_uuid"]).any():
        raise ValueError("More than one pick rate for the same event, map and agent")
    return events, pick_rates


if __name__ == "__main__":
    with connect() as conn:
        events, pick_rates = clean(conn)
        rebuild_tables(conn, "pro")
        events.to_sql("events", conn, if_exists="append", index=False)
        pick_rates.to_sql("pro_pick_rates", conn, if_exists="append", index=False)
    no_sample = pick_rates["maps_played"].isna().sum()
    print(f"events: loaded {len(events)} ({events['phase'].notna().sum()} with a phase, "
          f"{events['start_date'].notna().sum()} with dates)")
    print(f"pro_pick_rates: loaded {len(pick_rates)} ({no_sample} without a maps_played count)")
