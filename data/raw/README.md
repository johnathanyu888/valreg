# Raw data

Untouched downloads. Cleaning scripts read from here; nothing here is edited by hand.

## agents_YYYY-MM-DD.json

Saved by `collectors/valorant_api.py` from https://valorant-api.com (free, keyless,
community-run, not affiliated with Riot Games). One file per run.

## kaggle_vct/ (not in git, ~160 MB)

"Valorant Champion Tour 2021-2026 Data" by Ryan Luong (scraped from vlr.gg), MIT license.
Kaggle ref: `ryanluong1/valorant-champion-tour-2021-2023-data`. Downloaded 2026-11-22
(dataset last updated 2026-06-26).

To rebuild on another computer, run `python collectors/pro_data.py` from the project folder.
It downloads the zip and extracts only `vct_*/agents/*.csv` and `all_ids/*.csv` (the full
archive is ~1.3 GB unzipped, mostly per-match player stats this project doesn't use).

## manual/event_dates.csv

Hand-entered season order for the top-tier 2023-2026 events, because the Kaggle data has no
dates. `phase` is each event's position in its season (1 = first); events with the same phase
ran at the same time (e.g. the four regional Stage 1 leagues). This is what the forecast uses
to order events. `start_date`/`end_date` (YYYY-MM-DD) are optional extras, filled where known.
Names must match the Kaggle tournament names exactly.
Put the page each date came from in `source`. Liquipedia's terms forbid automated access to
its pages, so look dates up there in a browser and type them in; Wikipedia has a few.

## maps_YYYY-MM-DD.json

Saved by `collectors/valorant_api.py`. Includes non-competitive maps (Skirmish, The Range,
deathmatch maps); filter them out in cleaning.

## youtube_YYYY-MM-DD.json

Saved by `collectors/youtube.py` (YouTube Data API v3, needs `YOUTUBE_API_KEY` in `.env`).
One search per agent and competitive map, plus view counts for the videos found.
