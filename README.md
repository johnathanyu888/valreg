# valreg: Valorant pro meta tracker and pick-rate forecast

valreg collects public Valorant esports data, cleans it into a SQLite database, and forecasts
how often each agent will be picked on each map in the next pro phase, **with an honest 80%
margin of error**. A Streamlit site shows the forecast, how the meta has moved since 2023,
and agent playstyle groups.

**Research question:** which agents and maps are most popular in pro play, what playstyle groups
do agents fall into, and what predicts when an agent's pro popularity rises or falls?

## Results (honest version)

The forecast was chosen by comparing models on 2024 only, then tested once on the 9 phases
of 2025-2026, with every prediction made from earlier data only (walk-forward).

| | Average miss (MAE, percentage points) | 80% range: real values inside |
|---|---|---|
| Baseline: "same as last phase" | 8.54 | 78% |
| **Chosen: median linear regression** | **8.43** | **78%** (average width 18.9 pts) |

- The model beats the naive baseline by only **0.12 points**. That is essentially a tie, and the
  site says so: the pro meta mostly looks like last phase, drifting back toward each agent's recent
  average. The model's learned weights confirm it (about 0.5 x last phase + 0.4 x 3-phase average).
- The 80% ranges are calibrated from past misses and checked: 78% of 2025-2026 values fell inside.
- Forecasting a whole phase (all regions combined) instead of single regional events cut the error
  from 9.5 to 8.4 points, because single-region pick rates often rest on only 5-10 maps.
- Things that did **not** help (on 2024 validation): extra features (agent's all-maps popularity,
  sample size, gap since last played, years in pro play, event type), gradient boosting, separate
  error margins for small and large predictions. The likely missing ingredient is **patch history**.

## How it works

```
valorant-api.com ─┐                                ┌─> data/valreg.db (SQLite) ─> analysis/ ─> data/results/*.csv ─> Streamlit app
Kaggle VCT data ──┼─> collectors/ ─> data/raw/ ─> cleaning/
event phases ─────┘   (download)     (untouched)   (types, names -> IDs, checks)
(hand-made CSV)
```

1. **Collect** (`collectors/`): agents and maps from valorant-api.com; pro pick rates from the Kaggle
   dataset; a YouTube collector is ready but needs an API key.
2. **Clean** (`cleaning/`): keep whole-event rows for the 49 top-tier events of 2023-2026, turn "62%"
   into 62.0, match names like `kayo` to KAY/O, and stop loudly on bad data.
3. **Order** events by season phase (Kickoff -> Masters -> Stage 1 -> Masters -> Stage 2 -> Champions),
   from a hand-made file, because the source has no dates.
4. **Training table** (`analysis/features.py`): one row per agent, map and phase, with features built
   only from earlier phases.
5. **Model** (`analysis/forecast.py`): walk-forward validation, model chosen on 2024, tested on
   2025-2026, 80% ranges by split conformal prediction.
6. **Playstyles** (`analysis/clusters.py`): traits from ability descriptions, k-means clustering (first draft).

## Run it

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python collectors/valorant_api.py     # agents and maps
python collectors/pro_data.py         # Kaggle pro data (~84 MB download)
python run_pipeline.py                # database + model + results
streamlit run app/streamlit_app.py
```

## Two bugs worth telling

**Kaggle said "404 Not Found" to my script but not to my browser.** The same download URL worked from
PowerShell and failed from Python. Testing the request with and without a custom `User-Agent` header
showed Kaggle rejects the default `python-requests/x.y` identity. Fix: the collector sends its own
name (`valreg-collector/1.0`).

**Sorting events by ID would have leaked the future.** The data has no event dates, and vlr.gg
tournament IDs looked like a time order. Checking them against known dates showed they follow when the
event *page* was created: 2025 Masters Toronto and Champions have lower IDs than Stage 1, which was
played months earlier. A model trained in that order would "see" later events, and its test score
would look better than it really is. Fix: a hand-made season phase per event, checked against the 9
event dates Wikipedia gives.

## Data sources and credits

- [valorant-api.com](https://valorant-api.com): free community API (not affiliated with Riot).
- Kaggle: "Valorant Champion Tour 2021-2026 Data" by Ryan Luong (MIT license), scraped from vlr.gg.
- Wikipedia: dates of international events.
- Not used, because their terms don't allow automated collection: vlr.gg, Riot's websites,
  Liquipedia (by script). Reddit's API terms couldn't be verified, so it isn't used.

valreg is a student project and is not affiliated with or endorsed by Riot Games.

## Limitations

- Pro data stops in June 2026 (no Hush, no Summit).
- Patch changes and agent release dates aren't modeled yet.
- The next event's map pool is assumed to match the last phase's.
- Playstyle traits are keyword-based and need checking by hand; the groups overlap.
