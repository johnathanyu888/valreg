"""Train and score forecast models with walk-forward validation, then forecast the next phase.

WALK-FORWARD: for each test phase (every phase from FIRST_TEST_YEAR on), a model may learn
only from earlier phases, then predicts that phase. Nothing from the future is ever used.

SCORES (lower MAE is better):
    mae             mean absolute error in percentage points, all test rows
    mae_nontrivial  same, excluding the easy rows where the agent had 0% last time and 0% now
    coverage        share of real values that fell inside the model's 80% range (target: ~80%)
    width           average width of the 80% range, in percentage points

80% RANGE ("margin of error"), split conformal prediction:
    Before predicting phase s, the model is trained on phases before s-1 and predicts s-1.
    The 80th percentile of its misses on s-1 becomes the +/- margin for phase s.
    So the margin is also built only from the past, and `coverage` checks whether it's honest.

MODELS:
    same_as_last       baseline: predict the agent-map's previous pick rate
    rolling_avg_3      baseline: predict the average of its last 3 appearances
    linear_regression  learns weights for previous pick rate, rolling average, role and map,
                       by minimizing SQUARED error (ordinary least squares)
    median_linear      the same inputs, but minimizes ABSOLUTE error (median regression).
                       Matches the MAE metric: squared error pulls predictions toward the
                       average, so never-picked agents get predicted at ~2% instead of 0%.
    gradient_boosting  many small decision trees, each correcting the last; can learn curves

Every model and setting here was compared on the same 2025-2026 test phases, so a small
win could partly be luck from trying several models. `phases_won` shows how consistent it is.

Outputs go to data/results/ for the Streamlit app.

Run from the project folder:
    python analysis/forecast.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, QuantileRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder

from features import ROLLING_WINDOW, build_training_table, next_phase_features

FIRST_TEST_YEAR = 2025
COVERAGE = 0.80  # the error range should contain the real value 80% of the time
RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "results"

NUMERIC = ["prev_pick_rate", "rolling_avg"]
CATEGORICAL = ["role", "map_name"]


# ---------- models: each takes (train, test) and returns predictions for test ----------

def same_as_last(train, test):
    return test["prev_pick_rate"].to_numpy()


def rolling_avg(train, test):
    return test["rolling_avg"].to_numpy()


def make_learner(estimator):
    """Wrap a scikit-learn estimator: one-hot encode role and map, keep numbers as they are."""
    encode = ColumnTransformer([
        ("categories", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ("numbers", "passthrough", NUMERIC),
    ])
    return make_pipeline(encode, estimator)


def linear_regression(train, test):
    model = make_learner(LinearRegression()).fit(train[NUMERIC + CATEGORICAL], train["pick_rate"])
    return model.predict(test[NUMERIC + CATEGORICAL])


def median_linear(train, test):
    # quantile=0.5 -> predict the median; alpha=0 -> no penalty on the weights
    model = make_learner(QuantileRegressor(quantile=0.5, alpha=0, solver="highs"))
    model.fit(train[NUMERIC + CATEGORICAL], train["pick_rate"])
    return model.predict(test[NUMERIC + CATEGORICAL])


def gradient_boosting(train, test):
    model = make_learner(GradientBoostingRegressor(random_state=0))  # fixed seed = same result every run
    model.fit(train[NUMERIC + CATEGORICAL], train["pick_rate"])
    return model.predict(test[NUMERIC + CATEGORICAL])


MODELS = {
    "same_as_last": same_as_last,
    f"rolling_avg_{ROLLING_WINDOW}": rolling_avg,
    "linear_regression": linear_regression,
    "median_linear": median_linear,
    "gradient_boosting": gradient_boosting,
}
BASELINE_NAMES = ["same_as_last", f"rolling_avg_{ROLLING_WINDOW}"]


# ---------- prediction with an 80% range ----------

def predict_with_range(model, table, step, test):
    """Predict `test` (rows at `step`) using only earlier phases, with a calibrated +/- margin."""
    train = table[table["step"] < step]
    calib_train = table[table["step"] < step - 1]
    calib = table[table["step"] == step - 1]
    misses = np.abs(calib["pick_rate"].to_numpy() - model(calib_train, calib).clip(0, 100))
    margin = np.quantile(misses, COVERAGE)
    pred = model(train, test).clip(0, 100)  # pick rates can't go below 0 or above 100
    return pred, (pred - margin).clip(0, 100), (pred + margin).clip(0, 100), margin


def walk_forward(table):
    """Predictions for every test row from every model, in long format (one row per model per row)."""
    out = []
    for step in sorted(table.loc[table["year"] >= FIRST_TEST_YEAR, "step"].unique()):
        test = table[table["step"] == step]
        for name, model in MODELS.items():
            pred, low, high, margin = predict_with_range(model, table, step, test)
            out.append(test.assign(model=name, predicted=pred, low=low, high=high, margin=margin))
    return pd.concat(out, ignore_index=True)


def score(preds):
    """Summary scores per model (overall) and per model per phase."""
    p = preds.assign(
        error=(preds["pick_rate"] - preds["predicted"]).abs(),
        inside=preds["pick_rate"].between(preds["low"], preds["high"]),
        width=preds["high"] - preds["low"],
        trivial=(preds["pick_rate"] == 0) & (preds["prev_pick_rate"] == 0),
    )

    def summarize(g):
        return pd.Series({
            "rows": len(g),
            "mae": g["error"].mean(),
            "mae_nontrivial": g.loc[~g["trivial"], "error"].mean(),
            "coverage": g["inside"].mean(),
            "width": g["width"].mean(),
        })

    overall = p.groupby("model", sort=False).apply(summarize, include_groups=False).reset_index()
    per_phase = p.groupby(["model", "year", "phase"], sort=False).apply(summarize, include_groups=False).reset_index()

    # How many test phases each model beats the best baseline in (consistency check).
    base_mae = {m: overall.set_index("model").loc[m, "mae"] for m in BASELINE_NAMES}
    best_base = min(base_mae, key=base_mae.get)
    base_by_phase = per_phase[per_phase["model"] == best_base].set_index(["year", "phase"])["mae"]
    wins = per_phase.assign(won=per_phase["mae"].to_numpy()
                            < base_by_phase.loc[list(zip(per_phase["year"], per_phase["phase"]))].to_numpy())
    overall["phases_won"] = overall["model"].map(wins.groupby("model")["won"].sum()).astype(int)
    overall.loc[overall["model"] == best_base, "phases_won"] = 0
    overall["phases"] = per_phase.groupby("model", sort=False).size().to_numpy()
    return overall, per_phase


def forecast_next(table, best_model):
    """Forecast the phase after the newest one, for every model, with the 80% range."""
    nxt = next_phase_features()
    step = int(nxt["step"].iloc[0])
    out = []
    for name, model in MODELS.items():
        pred, low, high, margin = predict_with_range(model, table, step, nxt)
        out.append(nxt.assign(model=name, predicted=pred, low=low, high=high, margin=margin))
    result = pd.concat(out, ignore_index=True)
    result["best_model"] = result["model"] == best_model
    return result


def linear_weights(table):
    """The weights linear regression learns when trained on all data (for explanation)."""
    model = make_learner(LinearRegression()).fit(table[NUMERIC + CATEGORICAL], table["pick_rate"])
    names = model[0].get_feature_names_out()
    weights = pd.DataFrame({"feature": names, "weight": model[-1].coef_})
    intercept = pd.DataFrame({"feature": ["intercept"], "weight": [model[-1].intercept_]})
    return pd.concat([intercept, weights], ignore_index=True)


if __name__ == "__main__":
    table = build_training_table()
    preds = walk_forward(table)
    overall, per_phase = score(preds)
    best = overall.sort_values("mae").iloc[0]["model"]
    best_baseline = overall[overall["model"].isin(BASELINE_NAMES)].sort_values("mae").iloc[0]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    keep = ["year", "phase", "event", "map_name", "agent", "role", "pick_rate", "prev_pick_rate",
            "rolling_avg", "maps_played", "model", "predicted", "low", "high", "margin"]
    preds[keep].round(2).to_csv(RESULTS_DIR / "backtest_predictions.csv", index=False)
    overall.round(4).to_csv(RESULTS_DIR / "model_scores.csv", index=False)
    per_phase.round(4).to_csv(RESULTS_DIR / "model_scores_by_phase.csv", index=False)
    nxt = forecast_next(table, best)
    nxt[["map_name", "agent", "role", "prev_pick_rate", "rolling_avg", "model", "best_model",
         "predicted", "low", "high", "margin"]].round(2).to_csv(RESULTS_DIR / "next_phase_forecast.csv", index=False)
    linear_weights(table).round(4).to_csv(RESULTS_DIR / "linear_weights.csv", index=False)

    print(f"Walk-forward over {preds['step'].nunique()} test phases, {len(table)} training-table rows\n")
    print(overall.round(3).to_string(index=False))
    gain = best_baseline["mae"] - overall.set_index("model").loc[best, "mae"]
    print(f"\nBest model: {best}. Best baseline: {best_baseline['model']} "
          f"(MAE {best_baseline['mae']:.2f}). Improvement: {gain:.2f} percentage points.")
    print(f"Saved results to {RESULTS_DIR}")
