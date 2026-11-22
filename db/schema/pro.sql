-- Rebuilt by cleaning/load_pro_pick_rates.py from data/raw/kaggle_vct/ (Kaggle, vlr.gg).
DROP TABLE IF EXISTS pro_pick_rates;
DROP TABLE IF EXISTS events;

CREATE TABLE events (
    event_id INTEGER PRIMARY KEY,
    year     INTEGER NOT NULL,
    name       TEXT NOT NULL,     -- e.g. 'Valorant Masters Santiago 2026'
    phase      INTEGER,           -- order within the season (1 = first); same phase = same time.
                                  -- From data/raw/manual/event_dates.csv; NULL = not in the forecast scope
    start_date TEXT,              -- YYYY-MM-DD from data/raw/manual/event_dates.csv; NULL if not dated
    end_date   TEXT,              -- only dated events can be used by the forecast
    UNIQUE (year, name)           -- some names repeat across years (e.g. 2021 and 2022 LCQs)
);

-- One row per agent per event, for each map and for all maps combined.
-- Whole-event figures only (the source's 'All Stages' + 'All Match Types' rows).
CREATE TABLE pro_pick_rates (
    event_id    INTEGER NOT NULL REFERENCES events (event_id),
    map_uuid    TEXT REFERENCES maps (uuid),   -- NULL = all maps combined
    agent_uuid  TEXT NOT NULL REFERENCES agents (uuid),
    pick_rate   REAL NOT NULL CHECK (pick_rate BETWEEN 0 AND 100),  -- percent, e.g. 62.0
    maps_played INTEGER                        -- maps played at the event (on that map); sample size
);

CREATE UNIQUE INDEX pro_pick_rates_key
    ON pro_pick_rates (event_id, COALESCE(map_uuid, ''), agent_uuid);
