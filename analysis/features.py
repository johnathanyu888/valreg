"""Build the forecast training table: one row per agent, per map, per event.

Each row has the TARGET (the agent's pick rate on that map at that event) and the
FEATURES the model may use, built only from earlier phases so nothing leaks from
the future:
    prev_pick_rate   pick rate at the agent-map's last earlier appearance
    rolling_avg      average over its last ROLLING_WINDOW earlier appearances
    role, map_name   categories

Decisions (see CLAUDE.md, forecast section):
  - Scope: the 49 top-tier 2023-2026 events that have a phase.
  - Time order: year, then phase. Events in the same phase ran at the same time,
    so they are combined (weighted by maps played) when used as history.
  - Rows with no earlier appearance are dropped.

Run from the project folder to see a summary:
    python analysis/features.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "valreg.db"
ROLLING_WINDOW = 3  # how many earlier appearances the rolling average covers

QUERY = """
SELECT e.event_id, e.name AS event, e.year, e.phase,
       m.name AS map_name, a.name AS agent, a.role,
       p.map_uuid, p.agent_uuid, p.pick_rate, p.maps_played
FROM pro_pick_rates p
JOIN events e USING (event_id)
JOIN maps   m ON m.uuid = p.map_uuid
JOIN agents a ON a.uuid = p.agent_uuid
WHERE e.phase IS NOT NULL          -- forecast scope: top-tier 2023-2026
  AND p.map_uuid IS NOT NULL       -- per-map rows only (not 'all maps')
"""


def load_rows():
    """Per-map pick rates for in-scope events, with a global time step 0, 1, 2, ..."""
    with sqlite3.connect(DB_PATH) as conn:
        rows = pd.read_sql(QUERY, conn)
    # step numbers (year, phase) in time order: 2023 phase 1 -> 0, 2023 phase 2 -> 1, ...
    rows["step"] = rows.groupby(["year", "phase"]).ngroup()
    return rows


def history(rows):
    """One value per (step, map, agent): concurrent events combined, weighted by maps played.

    Also adds the rolling average over the last ROLLING_WINDOW appearances (including this one).
    `available_from` = step + 1, because a phase's results can only be used by LATER phases.
    """
    h = (rows.assign(weighted=rows["pick_rate"] * rows["maps_played"])
         .groupby(["step", "map_uuid", "agent_uuid"], as_index=False)
         .agg(weighted=("weighted", "sum"), maps=("maps_played", "sum")))
    h["value"] = h["weighted"] / h["maps"]
    h = h.sort_values("step")
    h["rolling_avg"] = (h.groupby(["map_uuid", "agent_uuid"])["value"]
                         .transform(lambda s: s.rolling(ROLLING_WINDOW, min_periods=1).mean()))
    h["available_from"] = h["step"] + 1
    return h[["available_from", "map_uuid", "agent_uuid", "value", "rolling_avg"]].rename(
        columns={"value": "prev_pick_rate"})


def build_training_table():
    """Return the training table (rows with no earlier appearance removed)."""
    rows = load_rows().sort_values("step")
    hist = history(rows).sort_values("available_from")
    # For each row, take the latest history entry with available_from <= this row's step,
    # i.e. the agent-map's most recent appearance in an EARLIER phase.
    table = pd.merge_asof(rows, hist, left_on="step", right_on="available_from",
                          by=["map_uuid", "agent_uuid"], direction="backward")
    table = table.dropna(subset=["prev_pick_rate"]).drop(columns="available_from")
    return table.sort_values(["step", "event", "map_name", "agent"]).reset_index(drop=True)


def next_phase_features():
    """Feature rows for the phase AFTER the newest one in the data, to forecast it.

    The next event's map pool isn't known yet, so this uses the maps played in the newest
    phase, and every agent with history on each of those maps.
    """
    rows = load_rows()
    last_step = rows["step"].max()
    hist = history(rows)
    latest = (hist.sort_values("available_from")
              .groupby(["map_uuid", "agent_uuid"], as_index=False).last())
    pool = rows.loc[rows["step"] == last_step, ["map_uuid", "map_name"]].drop_duplicates()
    agents = rows[["agent_uuid", "agent", "role"]].drop_duplicates()
    nxt = latest.merge(pool, on="map_uuid").merge(agents, on="agent_uuid")
    nxt["step"] = last_step + 1
    return nxt.drop(columns="available_from").sort_values(["map_name", "agent"]).reset_index(drop=True)


if __name__ == "__main__":
    all_rows = load_rows()
    table = build_training_table()
    print(f"{len(all_rows)} in-scope rows -> {len(table)} with history "
          f"({len(all_rows) - len(table)} dropped), {table['step'].nunique()} time steps")
    cols = ["year", "phase", "event", "map_name", "agent", "role",
            "pick_rate", "prev_pick_rate", "rolling_avg", "maps_played"]
    example = table[(table["agent"] == "Viper") & (table["map_name"] == "Split")]
    print("\nExample: Viper on Split over time")
    print(example[cols].round(1).to_string(index=False))
