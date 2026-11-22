"""Score forecast models on future phases with walk-forward validation.

Walk-forward: for each test phase (every phase from FIRST_TEST_YEAR on), a model may
learn only from earlier phases, then predicts that phase. The score is MAE (mean
absolute error) in percentage points: on average, how far the predicted pick rate is
from the real one. Lower is better.

So far: the two baselines that any real model must beat.
    same_as_last   predict the agent-map's previous pick rate
    rolling_avg    predict the average of its last few appearances
Neither baseline learns anything, so "training" is a no-op for them; the linear
regression will plug into the same loop.

Run from the project folder:
    python analysis/forecast.py
"""

import pandas as pd

from features import ROLLING_WINDOW, build_training_table

FIRST_TEST_YEAR = 2025

BASELINES = {
    "same_as_last": "prev_pick_rate",
    f"rolling_avg_{ROLLING_WINDOW}": "rolling_avg",
}


def walk_forward(table):
    """Return one row per test phase with each baseline's MAE on that phase."""
    results = []
    test_steps = sorted(table.loc[table["year"] >= FIRST_TEST_YEAR, "step"].unique())
    for step in test_steps:
        test = table[table["step"] == step]
        # train = table[table["step"] < step]   <- the regression will learn from this
        row = {"year": test["year"].iloc[0], "phase": test["phase"].iloc[0], "rows": len(test)}
        for name, column in BASELINES.items():
            row[name] = (test["pick_rate"] - test[column]).abs().mean()
        results.append(row)
    return pd.DataFrame(results)


if __name__ == "__main__":
    table = build_training_table()
    results = walk_forward(table)
    print("MAE in percentage points per test phase (lower is better):")
    print(results.round(2).to_string(index=False))
    overall = {name: (results[name] * results["rows"]).sum() / results["rows"].sum() for name in BASELINES}
    print("\nOverall MAE across all test rows:")
    for name, mae in overall.items():
        print(f"  {name:15s} {mae:.2f}")
