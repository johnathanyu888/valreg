"""Clean the newest raw maps file and load the competitive maps into the `maps` table.

valorant-api.com lists every map in the game, including Skirmish, The Range and
deathmatch-only maps. Competitive maps are the ones with bomb sites, which the API
describes in `tacticalDescription` (e.g. 'A/B Sites'). Maps without it are dropped.

Run from the project folder:
    python cleaning/load_maps.py
"""

from common import connect, name_key, newest_raw, rebuild_tables


def clean_maps(raw):
    """Keep competitive maps and return clean rows (tuples)."""
    rows = []
    for m in raw["data"]:
        sites = m.get("tacticalDescription")  # 'A/B Sites', 'A/B/C Sites' or None
        if not sites:
            continue
        rows.append((
            m["uuid"],
            m["displayName"],
            name_key(m["displayName"]),
            sites.replace(" Sites", ""),
        ))
    return rows


if __name__ == "__main__":
    path, raw = newest_raw("maps")
    rows = clean_maps(raw)
    with connect() as conn:
        rebuild_tables(conn, "maps")
        conn.executemany("INSERT INTO maps VALUES (?, ?, ?, ?)", rows)
    print(f"maps: kept {len(rows)} competitive of {len(raw['data'])} in {path.name}")
