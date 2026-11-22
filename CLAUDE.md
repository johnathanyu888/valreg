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
- Libraries so far: pandas, requests, scikit-learn, streamlit (pinned in `requirements.txt`).
- Virtual environment: `.venv` (activate with `.venv\Scripts\Activate.ps1`). It is never committed.
- Sync between my two computers is through GitHub only: `git pull` at the start of a session, commit and push at the end.
- Secrets (API keys) live in a `.env` file that is git-ignored, and later in GitHub Actions secrets if I automate. Never commit keys.
- I am new to Git. Explain Git commands when we use them and remind me to commit at the end of each session.

## Data sources

| Source | Use | Status and caveats |
|---|---|---|
| valorant-api.com | Agents, roles, abilities, maps (free, keyless, community-run) | Use agent UUID as the master ID everywhere. The maps endpoint includes non-competitive maps, so filter to the competitive pool. |
| Kaggle dataset "Valorant Champion Tour 2021-2026 Data" (by Ryan Luong, scraped from vlr.gg) | Pro pick rates by agent, map, tournament, stage, year | Backbone of the forecast. Columns seen: source_file, tournament, stage, match_type, map, agent, pick_rate, year. Inspect before trusting. |
| YouTube Data API v3 | Ranked-audience interest: views/day for videos about each agent | Free but quota-limited, and searches are the expensive calls. My understanding is about 100 searches per day, **to be verified in Google's docs**. Spread collection across days. |
| Google Trends via `pytrends` (optional) | Search interest over time | Unofficial library. Verify it works and its limits first. |
| Reddit (optional, light use only) | Mention counts | I do not want to rely on it because of rate limits. Verify current API terms first. |
| Patch history | Dates of buffs and nerfs per agent | No ready dataset. I will probably build it by hand or semi-manually from Riot's public patch notes. |

**Ruled out (do not propose again without discussing):**
- Riot's official Valorant match API: personal keys are not offered for Valorant, and production keys require a working public app, so it is closed to this project.
- tracker.gg: no public developer API and its terms restrict automated use. I may log a few ranked pick rates by hand weekly for my own time series.
- X/Twitter API: no useful free tier; reads are pay-per-use.

## Pipeline (how data flows)

1. **Collect** with plain Python scripts in `collectors/` (HTTP requests or file downloads). No AI is involved in scraping.
2. **Keep raw data untouched** in `data/raw/`.
3. **Clean** in `cleaning/`: inspect (`head`, `info`, `isna`), fix types (for example "54.69%" becomes 54.69), normalize names ("Kay/O", "KAY/O" and "Kayo" become one name), remove duplicates, validate (pick rates between 0 and 100), join to agent UUIDs. Cleaned results go into SQLite.
4. **Store** in SQLite (`data/valreg.db` or similar; the Day 1 script currently uses `data/valorant.db`, so decide on one name and keep it consistent). Planned tables: `agents`, `maps`, `events`, `patches`, `pro_pick_rates`, `youtube_videos`, `youtube_snapshots`. Data volume is tiny, so size is not a concern. API quota is the real limit.
5. **Analyze** in `analysis/` with pandas and scikit-learn.
6. **Present** in `app/` (Streamlit), which only reads precomputed results from the database or files. No live scraping on the website.
7. **Deploy** free on Streamlit Community Cloud, reading from the repo. A scheduled GitHub Action for weekly YouTube snapshots is an optional later extra.

Planned layout:

```
valreg/
  CLAUDE.md
  collectors/   # valorant_api.py, pro_data.py, youtube.py
  cleaning/
  db/           # schema.sql, loading scripts
  analysis/     # index.py, clusters.py, forecast.py
  app/          # Streamlit dashboard
  data/raw/     # untouched downloads
  requirements.txt
  .gitignore    # .venv/  .env  __pycache__/
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

### 3. Forecast (headline model)
- **Target:** an agent's pick rate on a given map at the next pro event.
- **Rows:** one agent on one map at one event. **Features:** previous event pick rate, rolling average, days since agent release, whether a patch changed the agent, role, map.
- **Validation:** split by time (train on earlier events, test on later). Never shuffle randomly. Walk-forward validation preferred.
- **Models, in order:** (a) baseline "same as last event," (b) rolling-average baseline, (c) linear regression, (d) gradient boosting (scikit-learn). Report **MAE in percentage points** for each and only claim improvement if the model truly beats the baselines.
- Explain regression, gradient boosting and train/test splitting to me when we reach them.

## Status

- Environment set up (Python, VS Code, Git, GitHub, venv). Repo is on GitHub with `requirements.txt`, `CLAUDE.md` and `.gitignore` (2026-11-22).
- The first push had failed because git needed a GitHub sign-in that Claude's session cannot answer, not because the remote was non-empty (it was empty). **Claude cannot push for me: I run `git push` myself** in my own terminal.
- `requirements.txt` was originally UTF-16 (from `pip freeze >` in PowerShell 5.1), which git treats as binary. It was re-encoded to UTF-8. Regenerate it with `pip freeze | Out-File -Encoding utf8 requirements.txt`.
- Day 1 code drafted (`collectors/valorant_api.py`): fetches playable agents from `https://valorant-api.com/v1/agents?isPlayableCharacter=true` and saves uuid, name and role into an `agents` table in SQLite. The save logic was tested with fake data, but **the live API call has not been tested yet.** **The file is not in the repo yet** (`collectors/` was empty on 2026-11-22); find the draft or rebuild it.

## Suggested order of small tasks

1. ~~Fix the first push and confirm the repo is on GitHub.~~ Done 2026-11-22.
2. Run the agents collector and inspect the database with a SQL query.
3. Load `agents` in pandas, and try `groupby` on role.
4. Write the maps collector (filter to the competitive pool).
5. Download the Kaggle dataset into `data/raw/`, load it and inspect it.
6. Cleaning step by step, then load into SQLite.
7. First plot, then a one-page Streamlit app.
8. YouTube API key, one search, then views/day for one agent, then all agents across several days.
9. Popularity Index, baseline forecast, linear regression, gradient boosting, clustering, quiz (optional).
10. README with screenshots, deployment, and a short write-up of one hard bug and how I fixed it (for interviews).

## Definition of done for each task

I can explain what changed and why, the code runs from a clean checkout, and the change is committed with a clear message.
