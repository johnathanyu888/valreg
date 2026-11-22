# Raw data

Untouched downloads. Cleaning scripts read from here; nothing here is edited by hand.

## agents_YYYY-MM-DD.json

Saved by `collectors/valorant_api.py` from https://valorant-api.com (free, keyless,
community-run, not affiliated with Riot Games). One file per run.

## kaggle_vct/ (not in git, ~160 MB)

"Valorant Champion Tour 2021-2026 Data" by Ryan Luong (scraped from vlr.gg), MIT license.
Kaggle ref: `ryanluong1/valorant-champion-tour-2021-2023-data`. Downloaded 2026-11-22
(dataset last updated 2026-06-26).

To rebuild on another computer, in PowerShell from the project folder:

```powershell
New-Item -ItemType Directory -Force data\raw\kaggle_vct
Invoke-WebRequest "https://www.kaggle.com/api/v1/datasets/download/ryanluong1/valorant-champion-tour-2021-2023-data" -OutFile data\raw\kaggle_vct\vct_2021-2026_2026-11-22.zip
```

Then extract only `vct_*/agents/*.csv` and `all_ids/*.csv` into `data/raw/kaggle_vct/`
(the full archive is ~1.3 GB unzipped, mostly per-match player stats this project doesn't use).
