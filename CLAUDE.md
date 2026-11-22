# valreg: project brief for Claude Code

## How to work with me (read this first)

I am a first-year Computer Science student at the University of Waterloo (term 1A) and a complete beginner in programming. This is a learning project, and I also want it to be a strong portfolio piece for internship applications (fintech such as RBC, and game companies such as Riot Games). I want to be **extremely involved in the inner workings of every aspect of this project.** That means:

- **Explain before you write.** Before creating or changing code, tell me what you are about to do and why, in plain language. Define any term or library I might not know (pandas, SQL, regression, and so on) the first time it appears.
- **Small steps.** I work 30 to 60 minutes a day to avoid burnout. Break work into tasks that fit in one short session. Never dump a large amount of code at once. Stop at natural stopping points and tell me exactly what the next step is.
- **Let me write the important parts.** For core logic (cleaning functions, SQL queries, the index formula, the model setup), walk me through it and let me type or modify it myself where reasonable. Give hints before answers when I'm trying to learn something.
- **Ask me before making design decisions.** Offer 2 to 3 options with trade-offs and a recommendation. Do not silently choose libraries, schemas, formulas or model types.
- **Check my understanding.** After a new concept, ask me one short question to confirm I understood. I need to be able to explain every line in an interview.
- **Be honest.** If a data source is unreliable, a result is weak, a model barely beats the baseline, or something I propose won't work, say so plainly. Never invent numbers, data or results. Do not oversell what the project shows.
- **Respect terms of service.** Do not scrape sites that prohibit it. Check a site's terms and robots.txt before proposing to scrape it, and tell me what you found.

## The project in one paragraph

**valreg** analyzes the popularity of Valorant agents and maps. It collects public data from several sources, cleans it into a SQLite database, computes a transparent Popularity Index, clusters agents into playstyles, and trains a model that forecasts an agent's pick rate on a given map at the next pro tournament. Results are shown on a Streamlit website. The pipeline is run by me on my own schedule (not a live service), and the site presents saved results as a dated snapshot ("data as of ...").

**Research question:** Which Valorant agents and maps are most popular, what playstyle groups do agents fall into, and what predicts when an agent's pro popularity rises or falls?

**Non-goals for v1:** cheating analysis, individual player stats, a live backend, neural networks, and analyzing the content of pro strategy videos (possible much later).

## Environment

- Windows on both my desktop PC and my laptop. Use PowerShell commands. Python 3.12+.
- Project folder: `C:\dev\valreg` (deliberately outside OneDrive). GitHub repo: `valreg`.
- Libraries so far: pandas, requests, scikit-learn, streamlit, altair (charts; pinned in `requirements.txt`).
- Virtual environment: `.venv` (activate with `.venv\Scripts\Activate.ps1`). It is never committed.
- Sync between my two computers is through GitHub only: `git pull` at the start of a session, commit and push at the end.
- Secrets (API keys) live in a `.env` file that is git-ignored, and later in GitHub Actions secrets if I automate. Never commit keys.
- I am new to Git. Explain Git commands when we use them and remind me to commit at the end of each session.

## Data sources

| Source | Use | Status and caveats |
|---|---|---|
| valorant-api.com | Agents, roles, abilities, maps (free, keyless, community-run) | In use (`collectors/valorant_api.py`). Agent UUID is the master ID. Maps include non-competitive ones; cleaning keeps maps with bomb sites (13). **25 of 30 agents have a placeholder release date (1970-01-01)**, stored as NULL. |
| Kaggle "Valorant Champion Tour 2021-2026 Data" (Ryan Luong, from vlr.gg, MIT) | Pro pick rates | In use (`collectors/pro_data.py`; ~160 MB, git-ignored). Real columns: Tournament, Stage, Match Type, Map, Agent, Pick Rate (year = folder). Mixes summary rows (All Stages/Match Types/Maps) with detail rows. **No dates; last updated 2026-06-26** (no Hush, no Summit). Kaggle 404s the default python-requests User-Agent. |
| Event phases and dates | Ordering events in time | Hand-made `data/raw/manual/event_dates.csv`: phase for all 49 top-tier 2023-2026 events; dates for 9 (from Wikipedia). vlr.gg tournament IDs follow page-creation order, not play order, so don't sort by them. |
| YouTube Data API v3 | Ranked-audience interest | Collector written (`collectors/youtube.py`), **not run: needs my API key in `.env`**. Verified: 100 search.list calls/day, resets midnight PT; one run uses 43 searches. No cleaning script yet. |
| Patch history | Buffs/nerfs per agent | Not started. By hand from patch notes (Riot's ToS bans scrapers on its sites). Most promising missing feature. |

**Ruled out (do not propose again without discussing):**
- Riot's official Valorant match API: personal keys are not offered for Valorant, and production keys require a working public app, so it is closed to this project.
- tracker.gg: no public developer API and its terms restrict automated use. I may log a few ranked pick rates by hand weekly for my own time series.
- X/Twitter API: no useful free tier; reads are pay-per-use.
- vlr.gg scraping: terms (Sept 2025) ban data mining and systematic retrieval without written permission (community@vlr.gg).
- Riot sites (playvalorant.com patch notes) by script: Riot ToS bans bots and scrapers. Reading by hand is fine.
- Liquipedia pages by script: its API terms forbid automated access to HTML pages; robots.txt blocks AI agents. Reading by hand is fine.
- Google Trends: `pytrends` was archived in April 2025; the official Trends API is an application-only alpha.
- Reddit: terms pages couldn't be read (403) on 2026-11-22; not verified, so not used. Recheck by hand before proposing.
- Twitch API: allowed with a registered app, but only gives per-game viewers, not per-agent data.

## Pipeline (how data flows)

1. **Collect** with plain Python scripts in `collectors/` (HTTP requests or file downloads). No AI is involved in scraping.
2. **Keep raw data untouched** in `data/raw/`.
3. **Clean** in `cleaning/`: inspect (`head`, `info`, `isna`), fix types (for example "54.69%" becomes 54.69), normalize names ("Kay/O", "KAY/O" and "Kayo" become one name), remove duplicates, validate (pick rates between 0 and 100), join to agent UUIDs. Cleaned results go into SQLite.
4. **Store** in SQLite `data/valreg.db` (git-ignored, rebuilt from raw every run). Tables: `agents`, `maps`, `events` (with `phase`, dates), `pro_pick_rates` (with `maps_played`). Planned: `patches`, `youtube_videos`, `youtube_snapshots`.
5. **Analyze** in `analysis/` with pandas and scikit-learn; results go to `data/results/*.csv` (committed).
6. **Present** in `app/streamlit_app.py`, which only reads `data/results/`. No live scraping on the website.
7. **Deploy** free on Streamlit Community Cloud, reading from the repo (not done yet).

`python run_pipeline.py` rebuilds everything from `data/raw/`: the three cleaning loaders, then `analysis/forecast.py` and `analysis/clusters.py`.

Layout:

```
valreg/
  CLAUDE.md  README.md  run_pipeline.py  requirements.txt  .gitignore  .env.example
  collectors/   # valorant_api.py, pro_data.py, youtube.py
  cleaning/     # common.py, load_agents.py, load_maps.py, load_pro_pick_rates.py
  db/schema/    # one .sql per loader (agents, maps, pro)
  analysis/     # features.py (training table), forecast.py (model + ranges), clusters.py
  app/          # streamlit_app.py
  data/raw/     # untouched downloads + manual/event_dates.csv (kaggle_vct/ is git-ignored)
  data/results/ # CSVs the app reads
```

## Analysis components

### 1. Popularity Index (agents and maps)
- YouTube signal: for each agent, run queries like "Valorant <agent> guide" (always include "Valorant" because names like Sage, Viper and Fade are ambiguous). Use **views per day since upload**, not cumulative views, over a fixed recent window (for example the last 90 days). Take the **median** of the top N videos so one viral video cannot dominate. Log-transform, then standardize. Keep timestamped snapshots so I build my own time series.
- Combine with pro pick rate (and optionally Google Trends and Reddit). Weights should come from the data (for example the first principal component, or a regression), not from hand-picking.
- Robustness check: show that agent rankings barely change under different weightings.
- Be explicit that there is no ground truth for "true popularity," so the index is a transparent composite. Ranked-audience interest and pro pick rate are different things; keep them as separate lenses, and test whether YouTube interest predicts pro pick rate at all. A null result is still a finding.

### 2. Playstyle clusters and optional quiz
- Tag each agent with traits (flash, dash, recon, healing, smoke, trap, aggressive or passive, and so on), partly by hand from ability descriptions.
- Cluster agents into 4 or 5 playstyles (k-means or hierarchical), and name the clusters.
- Optional quiz: the user's answers build a preference vector, matched to agents by similarity. For "on each map," use real pro pick rates by map as the popularity signal.
- Describe the quiz honestly as a **matching recommender**, not a validated predictor, because there is no player-level data linking quiz answers to picks.
- **Status (2026-11-22):** first draft in `analysis/clusters.py`. Traits come from keywords in valorant-api ability descriptions; k-means picks k=5 by silhouette, but separation is weak (silhouette 0.18) and some tags are wrong (e.g. Sova lands in "Mobility"). Next: review the tags by hand.

### 3. Forecast (headline model)
- **Target:** an agent's pick rate on a given map at the next pro event.
- **Rows:** one agent on one map at one event. **Features:** previous event pick rate, rolling average, days since agent release, whether a patch changed the agent, role, map.
- **Validation:** split by time (train on earlier events, test on later). Never shuffle randomly. Walk-forward validation preferred.
- **Models, in order:** (a) baseline "same as last event," (b) rolling-average baseline, (c) linear regression, (d) gradient boosting (scikit-learn). Report **MAE in percentage points** for each and only claim improvement if the model truly beats the baselines.
- Explain regression, gradient boosting and train/test splitting to me when we reach them.
- **Decided 2026-11-22:**
  - Scope: the 49 top-tier 2023-2026 events. Order comes from `phase` in `data/raw/manual/event_dates.csv` (year, then phase; same phase = concurrent).
  - Previous pick rate = agent's pick rate on that map at its **last earlier appearance** (most recent earlier phase where the agent-map was played). Concurrent events in a phase are combined, weighted by `maps_played`.
  - Rows with no previous value (~9%: first phase, new agents, new maps) are **dropped**. All models are scored on the same rows.
  - Validation: **walk-forward** over each phase from 2025 on (train on all earlier phases, predict the phase, step forward).
  - v1 features leave out days since release and patch changes (data missing); add them later and measure whether they help.
- **Changed later on 2026-11-22 (Claude, while I was away; review these):**
  - Target is now **phase-level**: an agent's pick rate on a map across a whole phase, all events combined (weighted by maps played). Single regional events rest on few maps and are too noisy. 3,348 rows.
  - Model selection is honest: candidates compared on **2024 (validation)**, the winner scored once on **2025-2026 (test)**.
  - Chosen model: **median linear regression** (quantile regression at 0.5; minimizes absolute error to match MAE) on previous pick rate, 3-appearance rolling average, role, map. Extra features (agent's all-maps rate, sample size, gap, appearances, years in pro, event type) did not help on validation. Gradient boosting was worse.
  - Test result: MAE **8.43** vs "same as last" baseline **8.54** (only 0.12 better; essentially a tie). Hard rows (not 0%→0%): 11.8 vs 12.1.
  - 80% range = split conformal: 80th percentile of the previous 3 phases' misses. Test coverage 78%, average width 18.9 pts. Separate margins per prediction size were tried and made ranges wider.

## Status

- Environment set up (Python, VS Code, Git, GitHub, venv). Repo is on GitHub with `requirements.txt`, `CLAUDE.md` and `.gitignore` (2026-11-22).
- The first push had failed because git needed a GitHub sign-in that Claude's session cannot answer, not because the remote was non-empty (it was empty). **Claude cannot push for me: I run `git push` myself** in my own terminal.
- `requirements.txt` was originally UTF-16 (from `pip freeze >` in PowerShell 5.1), which git treats as binary. It was re-encoded to UTF-8. Regenerate it with `pip freeze | Out-File -Encoding utf8 requirements.txt`.
- Done on 2026-11-22 (much of it written by Claude at my request, so **I still need to learn it**): collectors for valorant-api, Kaggle and YouTube; cleaning into SQLite; event phases; training table; walk-forward model selection and testing; 80% ranges; playstyle clusters (draft); Streamlit app (Forecast, Meta trends, Playstyles, Accuracy & method); README.
- On a new computer: `git pull`, then `python collectors/pro_data.py` (Kaggle data isn't in git), then `python run_pipeline.py`.
- Never commit with a Claude co-author line.

## Suggested order of small tasks

1. ~~Repo on GitHub; collectors; cleaning into SQLite; Kaggle data; first app; baseline forecast and regression.~~ Done 2026-11-22.
2. **Learn what was built**, one file per session: `features.py` (`history()` and `merge_asof`: how the future is kept out), `forecast.py` (walk-forward, validation vs test, `add_range()`), `clusters.py`, the app.
3. Check the phase order on Liquipedia by hand (especially the 2023 Champions China Qualifier) and vlr.gg's definition of "pick rate".
4. Patch history by hand from patch notes, then measure if it improves the forecast on 2024 validation.
5. Review the playstyle trait tags by hand; rerun `analysis/clusters.py`.
6. YouTube API key -> run `collectors/youtube.py` -> write a YouTube cleaning script -> Popularity Index.
7. Add screenshots to the README; deploy on Streamlit Community Cloud.
8. Optional: quiz.

## Definition of done for each task

I can explain what changed and why, the code runs from a clean checkout, and the change is committed with a clear message.
