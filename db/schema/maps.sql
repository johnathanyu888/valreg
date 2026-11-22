-- Rebuilt by cleaning/load_maps.py from data/raw/maps_*.json (valorant-api.com).
-- Competitive maps only (maps with bomb sites).
DROP TABLE IF EXISTS maps;

CREATE TABLE maps (
    uuid     TEXT PRIMARY KEY,      -- ID from valorant-api.com
    name     TEXT NOT NULL UNIQUE,  -- e.g. 'Ascent'
    name_key TEXT NOT NULL UNIQUE,  -- normalized name for matching other sources, e.g. 'ascent'
    sites    TEXT NOT NULL          -- 'A/B' or 'A/B/C'
);
