"""Clean the newest raw agents file and load it into the `agents` table.

Reads the most recent data/raw/agents_YYYY-MM-DD.json (saved by
collectors/valorant_api.py), keeps the fields the project uses, fixes known data
problems, and rebuilds the `agents` table in data/valreg.db.

Run from the project folder:
    python cleaning/load_agents.py
"""

from common import connect, name_key, newest_raw, rebuild_tables

# valorant-api.com uses 1970-01-01 (the Unix "zero" date) when it has no real date.
PLACEHOLDER_DATE = "1970-01-01"


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


if __name__ == "__main__":
    path, raw = newest_raw("agents")
    rows = clean_agents(raw)
    with connect() as conn:
        rebuild_tables(conn, "agents")
        conn.executemany("INSERT INTO agents VALUES (?, ?, ?, ?, ?)", rows)
    missing = [r[1] for r in rows if r[4] is None]
    print(f"agents: loaded {len(rows)} from {path.name}; {len(missing)} have no real release date")
