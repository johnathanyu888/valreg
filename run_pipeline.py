"""Rebuild the whole database from data/raw/ by running every cleaning script in order.

Order matters: pro pick rates are joined to agent and map UUIDs, so those load first.
Collecting new raw data is a separate step (the scripts in collectors/).

Run from the project folder:
    python run_pipeline.py
"""

import subprocess
import sys
from pathlib import Path

CLEANING_DIR = Path(__file__).resolve().parent / "cleaning"

STEPS = [
    "load_agents.py",
    "load_maps.py",
    "load_pro_pick_rates.py",
]

if __name__ == "__main__":
    for step in STEPS:
        # check=True stops the pipeline if a step fails, instead of loading on top of bad data.
        subprocess.run([sys.executable, str(CLEANING_DIR / step)], check=True)
    print("Pipeline finished.")
