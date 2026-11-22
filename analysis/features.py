"""Build the forecast training table: one row per agent, per map, per PHASE.

WHAT WE FORECAST: an agent's pick rate on a map across a whole phase of the season, with
all events in that phase combined (weighted by maps played). Example: "Viper on Split during
2025 Stage 1, all four regional leagues together". Single regional events often rest on
5-10 maps, so their pick rates are noisy; combining a phase's events gives a steadier,
more predictable number (test MAE 8.4 vs 9.5 points per single event).

Each row has the TARGET (pick_rate) and FEATURES built only from EARLIER phases:
    prev_pick_rate       pick rate at the agent-map's last earlier appearance
    rolling_avg          average over its last ROLLING_WINDOW earlier appearances
    prev_maps            maps played behind prev_pick_rate (how reliable it is)
    appearances          how many earlier phases the agent-map was played in
    gap                  phases since it was last played (maps rotate out and back in)
    agent_all_maps_prev  the agent's pick rate across ALL maps at its last earlier phase
    years_in_pro         years since the agent was first picked in pro play (2021+ data);
                         stands in for release date, which valorant-api.com lacks
    role, map_name       categories
    event_type           'international' (Masters/Champions/LOCK//IN) or 'regional' phase

Decisions (see CLAUDE.md, forecast section):
  - Scope: the 49 top-tier 2023-2026 events that have a phase.
  - Time order: year, then phase.
  - Rows with no earlier appearance are dropped.

Run from the project folder to see a summary:
    python analysis/features.py
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "valreg.db"
ROLLING_WINDOW = 3  # how many earlier appearances the rolling average covers

NUMERIC = ["prev_pick_rate", "rolling_avg", "prev_maps", "appearances", "gap",
           "agent_all_maps_prev", "years_in_pro"]
CATEGORICAL = ["role", "map_name", "event_type"]
REGIONS = ("americas", "emea", "pacific", "china")

EVENT_QUERY = """
SELECT e.name AS event, e.year, e.phase,
       m.name AS map_name, a.name AS agent, a.role,
       p.map_uuid, p.agent_uuid, p.pick_rate, p.maps_played
FROM pro_pick_rates p
JOIN events e USING (event_id)
JOIN maps   m ON m.uuid = p.map_uuid
JOIN agents a ON a.uuid = p.agent_uuid
WHERE e.phase IS NOT NULL          -- forecast scope: top-tier 2023-2026
  AND p.map_uuid IS NOT NULL       -- per-map rows only (not 'all maps')
"""

ALL_MAPS_QUERY = """
SELECT e.year, e.phase, p.agent_uuid, p.pick_rate, p.maps_played
FROM pro_pick_rates p JOIN events e USING (event_id)
WHERE e.phase IS NOT NULL AND p.map_uuid IS NULL
"""

FIRST_PICK_QUERY = """
SELECT p.agent_uuid, MIN(e.year) AS first_year
FROM pro_pick_rates p JOIN events e USING (event_id)
WHERE p.pick_rate > 0
GROUP BY p.agent_uuid
"""


def query(sql):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(sql, conn)


def add_steps(df):
    """Global time step 0, 1, 2, ... in (year, phase) order."""
    phases = query("SELECT DISTINCT year, phase FROM events WHERE phase IS NOT NULL")
    step_of = {yp: i for i, yp in enumerate(sorted(zip(phases["year"], phases["phase"])))}
    df["step"] = [step_of[(y, p)] for y, p in zip(df["year"], df["phase"])]
    return df


def combine_by_step(df, keys):
    """One value per step and key: events in the same phase combined, weighted by maps played."""
    g = (df.assign(weighted=df["pick_rate"] * df["maps_played"])
         .groupby(["step", *keys], as_index=False)
         .agg(weighted=("weighted", "sum"), maps=("maps_played", "sum")))
    g["value"] = g["weighted"] / g["maps"]
    return g.drop(columns="weighted")


def phase_label(events):
    """'Valorant Masters Toronto 2025', or 'VCT 2025: Stage 1 (all regions)' for regional phases."""
    names = sorted(set(events))
    if len(names) == 1:
        return names[0]
    stripped = set()
    for n in names:
        for r in REGIONS:
            n = n.replace(r.capitalize() + " ", "").replace(r.upper() + " ", "")
        stripped.add(n.replace("Champions Tour", "VCT"))
    return " / ".join(sorted(stripped)) + " (all regions)"


def load_rows():
    """Phase-level pick rates: one row per (phase, map, agent), events combined."""
    ev = add_steps(query(EVENT_QUERY))
    rows = combine_by_step(ev, ["map_uuid", "agent_uuid"]).rename(
        columns={"value": "pick_rate", "maps": "maps_played"})
    per_step = ev.groupby("step").agg(year=("year", "first"), phase=("phase", "first"),
                                      phase_name=("event", phase_label))
    per_step["event_type"] = ["regional" if "all regions" in n else "international" for n in per_step["phase_name"]]
    names = ev[["map_uuid", "map_name", "agent_uuid", "agent", "role"]].drop_duplicates()
    return rows.merge(per_step, left_on="step", right_index=True).merge(names, on=["map_uuid", "agent_uuid"])


def history(rows):
    """Per (map, agent) history entries, each usable only from the NEXT step on."""
    h = rows.sort_values("step").copy()
    grp = h.groupby(["map_uuid", "agent_uuid"])
    h["rolling_avg"] = grp["pick_rate"].transform(lambda s: s.rolling(ROLLING_WINDOW, min_periods=1).mean())
    h["appearances"] = grp.cumcount() + 1
    h["last_step"] = h["step"]
    h["available_from"] = h["step"] + 1  # a phase's results can only be used by LATER phases
    return h.rename(columns={"pick_rate": "prev_pick_rate", "maps_played": "prev_maps"})[
        ["available_from", "map_uuid", "agent_uuid", "prev_pick_rate", "rolling_avg",
         "prev_maps", "appearances", "last_step"]].sort_values("available_from")


def agent_history():
    """Per agent: pick rate across all maps at each phase, usable from the next phase on."""
    a = combine_by_step(add_steps(query(ALL_MAPS_QUERY)), ["agent_uuid"])
    a["available_from"] = a["step"] + 1
    return a.rename(columns={"value": "agent_all_maps_prev"})[
        ["available_from", "agent_uuid", "agent_all_maps_prev"]].sort_values("available_from")


def attach_features(rows):
    """Add every feature to `rows` (which must have step, year, map_uuid, agent_uuid)."""
    out = pd.merge_asof(rows.sort_values("step"), history(load_rows()),
                        left_on="step", right_on="available_from",
                        by=["map_uuid", "agent_uuid"], direction="backward").drop(columns="available_from")
    out = pd.merge_asof(out.sort_values("step"), agent_history(),
                        left_on="step", right_on="available_from",
                        by="agent_uuid", direction="backward").drop(columns="available_from")
    out["gap"] = out["step"] - out["last_step"]
    out = out.merge(query(FIRST_PICK_QUERY), on="agent_uuid", how="left")
    out["years_in_pro"] = (out["year"] - out["first_year"]).clip(lower=0)
    out["agent_all_maps_prev"] = out["agent_all_maps_prev"].fillna(out["prev_pick_rate"])
    return out.drop(columns=["last_step", "first_year"])


def build_training_table():
    """Return the training table (rows with no earlier appearance removed)."""
    table = attach_features(load_rows()).dropna(subset=["prev_pick_rate"])
    return table.sort_values(["step", "map_name", "agent"]).reset_index(drop=True)


def next_phase_features(event_type="international"):
    """Feature rows for the phase AFTER the newest one, to forecast it.

    The next event (Masters London 2026) is international. Its map pool isn't in the data,
    so this uses the maps played in the newest phase and every agent with history on them.
    """
    rows = load_rows()
    last = rows[rows["step"] == rows["step"].max()]
    pairs = rows.loc[rows["map_uuid"].isin(last["map_uuid"]),
                     ["map_uuid", "map_name", "agent_uuid", "agent", "role"]].drop_duplicates()
    nxt = pairs.assign(step=int(last["step"].iloc[0]) + 1, year=int(last["year"].iloc[0]), event_type=event_type)
    nxt = attach_features(nxt).dropna(subset=["prev_pick_rate"])
    return nxt.sort_values(["map_name", "agent"]).reset_index(drop=True)


if __name__ == "__main__":
    table = build_training_table()
    print(f"{len(table)} rows (agent x map x phase with history), {table['step'].nunique()} phases")
    print(table.drop_duplicates("step")[["step", "year", "phase", "event_type", "phase_name"]].to_string(index=False))
    print("\nFeature summary:")
    print(table[NUMERIC].describe().round(1).to_string())
    print("Missing values:", int(table[NUMERIC + CATEGORICAL].isna().sum().sum()))
