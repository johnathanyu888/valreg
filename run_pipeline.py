"""Rebuild everything from data/raw/: the database, then the analysis results for the app.

Order matters: pro pick rates are joined to agent and map UUIDs, so those load first;
the analysis reads the finished database.
Collecting new raw data is a separate step (the scripts in collectors/).

Run from the project folder:
    python run_pipeline.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STEPS = [
    "cleaning/load_agents.py",
    "cleaning/load_maps.py",
    "cleaning/load_pro_pick_rates.py",
    "analysis/forecast.py",   # chooses and trains the model, writes data/results/
    "analysis/clusters.py",   # agent playstyle groups, writes data/results/agent_clusters.csv
]

if __name__ == "__main__":
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        # check=True stops the pipeline if a step fails, instead of building on top of bad data.
        subprocess.run([sys.executable, str(ROOT / step)], check=True)
    print("\nPipeline finished.")
