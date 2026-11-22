-- valreg database schema (SQLite).
-- Tables are rebuilt from data/raw/ by the cleaning scripts, so it is safe to drop them.

DROP TABLE IF EXISTS agents;

CREATE TABLE agents (
    uuid         TEXT PRIMARY KEY,  -- master ID from valorant-api.com, used to join every source
    name         TEXT NOT NULL UNIQUE,  -- display name as the API spells it, e.g. 'KAY/O'
    name_key     TEXT NOT NULL UNIQUE,  -- normalized name for matching other sources, e.g. 'kayo'
    role         TEXT NOT NULL,     -- Duelist, Initiator, Sentinel or Controller
    release_date TEXT               -- YYYY-MM-DD, or NULL when the API has no real date
);
