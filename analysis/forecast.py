"""Choose, train and score the forecast model, then forecast the next phase with an 80% range.

WHAT IS FORECAST: an agent's pick rate on a map across the next phase (see features.py).

HONEST MODEL SELECTION (three separate time periods):
    validation  2024 phases       candidates are compared here; the best one is chosen here
    test        2025-2026 phases  the chosen model is scored here, once (never used to choose)
    forecast    next phase        the chosen model, trained on everything, predicts it
Every prediction uses only earlier phases (walk-forward): the model is retrained before
each phase on all phases before it.

SCORES (lower MAE is better):
    mae             mean absolute error in percentage points
    mae_nontrivial  same, excluding the easy rows where the agent had 0% last time and 0% now
    coverage        share of real values inside the 80% range (should be close to 80%)
    width           average width of the 80% range, in percentage points

80% RANGE ("margin of error"), split conformal prediction:
    For each phase, take the model's walk-forward misses on the previous CALIB_PHASES phases.
    Their 80th percentile is the +/- margin. Built from the past only; `coverage` on the test
    phases checks that it's honest. (Separate margins for small/large predictions were tried
    and made the ranges wider, so one margin is used.)

Outputs go to data/results/ for the Streamlit app.

Run from the project folder:
    python analysis/forecast.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import QuantileRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder

from features import (ALL_MAPS_QUERY, CATEGORICAL, NUMERIC, add_steps, build_training_table, combine_by_step,
                      load_rows, next_phase_features, query)

VALIDATION_YEAR = 2024
TEST_FROM_YEAR = 2025
FIRST_PREDICTED_STEP = 2   # earliest phase to predict (needs at least one phase of training data)
COVERAGE = 0.80
CALIB_PHASES = 3           # how many previous phases calibrate the margin
RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "results"

V1_NUMERIC, V1_CATEGORICAL = ["prev_pick_rate", "rolling_avg"], ["role", "map_name"]


# ---------- candidate models ----------

class Learner:
    """One-hot encode the categories, pass numbers through, then fit a scikit-learn estimator."""

    def __init__(self, make_estimator, numeric, categorical):
        self.make_estimator, self.columns, self.categorical = make_estimator, numeric + categorical, categorical
        self.numeric = numeric

    def pipeline(self):
        encode = ColumnTransformer([
            ("categories", OneHotEncoder(handle_unknown="ignore", sparse_output=False), self.categorical),
            ("numbers", "passthrough", self.numeric)])
        return make_pipeline(encode, self.make_estimator())

    def __call__(self, train, test):
        model = self.pipeline().fit(train[self.columns], train["pick_rate"])
        return model.predict(test[self.columns])


def baseline(column):
    return lambda train, test: test[column].to_numpy()


def median_linear():
    # median regression: minimizes ABSOLUTE error, matching the MAE score.
    # (ordinary least squares minimizes squared error and pulls predictions toward the average)
    return QuantileRegressor(quantile=0.5, alpha=0, solver="highs")


def boosting():
    return HistGradientBoostingRegressor(learning_rate=0.05, max_iter=300, max_leaf_nodes=15,
                                         min_samples_leaf=40, random_state=0)


CANDIDATES = {
    "same_as_last": baseline("prev_pick_rate"),
    "rolling_avg_3": baseline("rolling_avg"),
    "median_linear_v1": Learner(median_linear, V1_NUMERIC, V1_CATEGORICAL),
    "median_linear": Learner(median_linear, NUMERIC, CATEGORICAL),
    "gradient_boosting": Learner(boosting, NUMERIC, CATEGORICAL),
}
BASELINES = ["same_as_last", "rolling_avg_3"]


# ---------- walk-forward predictions and margins ----------

def walk_forward(table, model):
    """Predict every phase from FIRST_PREDICTED_STEP on, each from a model trained on earlier phases."""
    out = []
    for step in range(FIRST_PREDICTED_STEP, table["step"].max() + 1):
        train, test = table[table["step"] < step], table[table["step"] == step]
        if len(test):
            out.append(test.assign(predicted=np.clip(model(train, test), 0, 100)))
    return pd.concat(out, ignore_index=True)


def add_range(preds, history_preds, step):
    """Attach low/high to predictions at `step`, calibrated on the previous CALIB_PHASES phases."""
    calib = history_preds[(history_preds["step"] < step) & (history_preds["step"] >= step - CALIB_PHASES)]
    margin = np.quantile((calib["pick_rate"] - calib["predicted"]).abs(), COVERAGE)
    return preds.assign(margin=margin, low=np.clip(preds["predicted"] - margin, 0, 100),
                        high=np.clip(preds["predicted"] + margin, 0, 100))


def with_ranges(wf):
    """Ranges for every walk-forward phase that has enough earlier phases to calibrate on."""
    steps = [s for s in sorted(wf["step"].unique()) if s - CALIB_PHASES >= FIRST_PREDICTED_STEP]
    return pd.concat([add_range(wf[wf["step"] == s], wf, s) for s in steps], ignore_index=True)


def score(p):
    trivial = (p["pick_rate"] == 0) & (p["prev_pick_rate"] == 0)
    err = (p["pick_rate"] - p["predicted"]).abs()
    return {"rows": len(p), "mae": err.mean(), "mae_nontrivial": err[~trivial].mean(),
            "coverage": p["pick_rate"].between(p["low"], p["high"]).mean(),
            "width": (p["high"] - p["low"]).mean()}


def feature_importance(table, learner):
    """How much MAE gets worse when each input is shuffled (trained before, tested on the last 3 phases)."""
    last = table["step"].max()
    train, test = table[table["step"] <= last - 3], table[table["step"] > last - 3]
    model = learner.pipeline().fit(train[learner.columns], train["pick_rate"])
    r = permutation_importance(model, test[learner.columns], test["pick_rate"],
                               scoring="neg_mean_absolute_error", n_repeats=5, random_state=0)
    return (pd.DataFrame({"feature": learner.columns, "mae_increase": r.importances_mean})
            .sort_values("mae_increase", ascending=False))


if __name__ == "__main__":
    table = build_training_table()
    rows, walks = [], {}
    for name, model in CANDIDATES.items():
        print(f"walk-forward: {name} ...", flush=True)
        walks[name] = walk_forward(table, model)
        r = with_ranges(walks[name])
        val, test = r[r["year"] == VALIDATION_YEAR], r[r["year"] >= TEST_FROM_YEAR]
        rows.append({"model": name, "baseline": name in BASELINES,
                     **{f"val_{k}": v for k, v in score(val).items() if k != "rows"},
                     **{f"test_{k}": v for k, v in score(test).items()}})
    scores = pd.DataFrame(rows)
    best = scores.sort_values("val_mae").iloc[0]["model"]          # chosen on VALIDATION only
    scores["chosen"] = scores["model"] == best
    best_base = scores[scores["baseline"]].sort_values("test_mae").iloc[0]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    scores.round(4).to_csv(RESULTS_DIR / "model_scores.csv", index=False)

    wf = walks[best]
    r = with_ranges(wf)
    test_rows = r[r["year"] >= TEST_FROM_YEAR]
    keep = ["step", "year", "phase", "phase_name", "event_type", "map_name", "agent", "role",
            "pick_rate", "prev_pick_rate", "maps_played", "predicted", "low", "high", "margin"]
    test_rows[keep].round(2).to_csv(RESULTS_DIR / "backtest_predictions.csv", index=False)
    per_phase = (test_rows.groupby(["step", "year", "phase", "phase_name"])
                 .apply(lambda g: pd.Series(score(g)), include_groups=False).reset_index())
    per_phase.round(4).to_csv(RESULTS_DIR / "test_scores_by_phase.csv", index=False)

    nxt = next_phase_features()
    nxt["predicted"] = np.clip(CANDIDATES[best](table, nxt), 0, 100)
    nxt = add_range(nxt, wf, int(nxt["step"].iloc[0]))
    nxt[["map_name", "agent", "role", "prev_pick_rate", "rolling_avg", "agent_all_maps_prev",
         "predicted", "low", "high", "margin"]].round(2).to_csv(RESULTS_DIR / "next_phase_forecast.csv", index=False)

    # History for the app's trend charts: per map, and across all maps, for every phase.
    hist = load_rows()
    hist[["step", "year", "phase", "phase_name", "event_type", "map_name", "agent", "role", "pick_rate",
          "maps_played"]].round(2).to_csv(RESULTS_DIR / "phase_pick_rates.csv", index=False)
    overall = combine_by_step(add_steps(query(ALL_MAPS_QUERY)), ["agent_uuid"]).rename(
        columns={"value": "pick_rate", "maps": "maps_played"})
    overall = overall.merge(hist[["agent_uuid", "agent", "role"]].drop_duplicates(), on="agent_uuid").merge(
        hist[["step", "phase_name"]].drop_duplicates(), on="step")
    overall[["step", "phase_name", "agent", "role", "pick_rate", "maps_played"]].round(2).to_csv(
        RESULTS_DIR / "agent_pick_rates.csv", index=False)

    if isinstance(CANDIDATES[best], Learner):
        feature_importance(table, CANDIDATES[best]).round(4).to_csv(RESULTS_DIR / "feature_importance.csv", index=False)

    pd.set_option("display.width", 200)
    print("\n" + scores.round(3).to_string(index=False))
    b = scores.set_index("model").loc[best]
    print(f"\nChosen on 2024 validation: {best}")
    print(f"Test 2025-2026: MAE {b['test_mae']:.2f} vs best baseline {best_base['model']} "
          f"{best_base['test_mae']:.2f} (improvement {best_base['test_mae'] - b['test_mae']:.2f} pts)")
    print(f"80% range: coverage {b['test_coverage']:.1%}, average width {b['test_width']:.1f} pts, "
          f"next-phase margin +/-{nxt['margin'].iloc[0]:.1f} pts")
    print(f"Saved results to {RESULTS_DIR}")
