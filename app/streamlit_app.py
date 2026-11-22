"""valreg prototype: pro pick-rate forecasts with an 80% margin of error.

Reads only precomputed files in data/results/ (made by analysis/forecast.py).
No live data fetching happens here.

Run from the project folder:
    streamlit run app/streamlit_app.py
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RESULTS = Path(__file__).resolve().parent.parent / "data" / "results"

MODEL_LABELS = {
    "same_as_last": "Baseline: same as last event",
    "rolling_avg_3": "Baseline: average of last 3",
    "linear_regression": "Linear regression",
    "median_linear": "Median linear regression",
    "gradient_boosting": "Gradient boosting",
}
BASELINES = ["same_as_last", "rolling_avg_3"]

st.set_page_config(page_title="valreg: Valorant pro pick-rate forecast", layout="wide")


@st.cache_data
def load():
    scores = pd.read_csv(RESULTS / "model_scores.csv")
    by_phase = pd.read_csv(RESULTS / "model_scores_by_phase.csv")
    backtest = pd.read_csv(RESULTS / "backtest_predictions.csv")
    forecast = pd.read_csv(RESULTS / "next_phase_forecast.csv")
    weights = pd.read_csv(RESULTS / "linear_weights.csv")
    for df in (scores, by_phase, backtest, forecast):
        df["model_label"] = df["model"].map(MODEL_LABELS)
    return scores, by_phase, backtest, forecast, weights


scores, by_phase, backtest, forecast, weights = load()
best = forecast.loc[forecast["best_model"], "model"].iloc[0]
s = scores.set_index("model")
base = s.loc[BASELINES, "mae"].idxmin()

st.title("valreg: Valorant pro pick-rate forecast")
st.caption(
    "Prototype. Pro data: Kaggle 'Valorant Champion Tour 2021-2026 Data' (scraped from vlr.gg), "
    "last updated 2026-06-26. Agents and maps: valorant-api.com. Not affiliated with Riot Games."
)

c1, c2, c3, c4 = st.columns([1.6, 1, 1, 1])
c1.metric("Best model", MODEL_LABELS[best].replace(" regression", ""))
c2.metric("Typical miss (MAE)", f"{s.loc[best, 'mae']:.1f} pts",
          delta=f"{s.loc[best, 'mae'] - s.loc[base, 'mae']:+.2f} vs baseline", delta_color="inverse")
c3.metric("80% range actually covered", f"{s.loc[best, 'coverage']:.0%}")
c4.metric("Test phases beating baseline", f"{int(s.loc[best, 'phases_won'])} of {int(s.loc[best, 'phases'])}")

tab_forecast, tab_accuracy, tab_backtest, tab_about = st.tabs(
    ["Next event forecast", "How accurate is it?", "Check past predictions", "How it works"])

# ---------------- Next event forecast ----------------
with tab_forecast:
    st.subheader("Forecast for the next phase after VCT 2026 Stage 1 (Masters London 2026)")
    st.write(
        "Predicted pick rate for each agent on each map, with an **80% range**: in testing on "
        f"2025-2026 events, the real value landed inside this kind of range "
        f"{s.loc[best, 'coverage']:.0%} of the time. The map pool for the next event isn't in the "
        "data, so these are the 8 maps played in VCT 2026 Stage 1."
    )
    left, right = st.columns([1, 3])
    with left:
        map_name = st.selectbox("Map", sorted(forecast["map_name"].unique()))
        model = st.selectbox("Model", list(MODEL_LABELS), index=list(MODEL_LABELS).index(best),
                             format_func=MODEL_LABELS.get)
        top_n = st.slider("Agents shown", 5, 30, 12)
    f = (forecast[(forecast["map_name"] == map_name) & (forecast["model"] == model)]
         .sort_values("predicted", ascending=False).head(top_n))
    with right:
        y = alt.Y("agent:N", sort=list(f["agent"]), title=None)
        bars = alt.Chart(f).mark_rule(strokeWidth=8, opacity=0.6, color="#8da4c4").encode(
            y=y, x=alt.X("low:Q", title="Pick rate (%)", scale=alt.Scale(domain=[0, 100])), x2="high:Q",
            tooltip=["agent", "role", alt.Tooltip("predicted:Q", format=".1f"),
                     alt.Tooltip("low:Q", format=".1f"), alt.Tooltip("high:Q", format=".1f"),
                     alt.Tooltip("prev_pick_rate:Q", title="last time", format=".1f")])
        points = alt.Chart(f).mark_point(filled=True, size=90).encode(y=y, x="predicted:Q", color="role:N")
        last = alt.Chart(f).mark_tick(color="gray", thickness=2, size=14).encode(y=y, x="prev_pick_rate:Q")
        st.altair_chart((bars + points + last).properties(height=28 * len(f) + 40), width="stretch")
        st.caption("Dot = prediction, blue bar = 80% range, grey tick = pick rate at its last appearance.")
    st.dataframe(
        f[["agent", "role", "prev_pick_rate", "predicted", "low", "high"]].rename(columns={
            "prev_pick_rate": "Last time (%)", "predicted": "Predicted (%)", "low": "80% low", "high": "80% high"}),
        hide_index=True, width="stretch")

# ---------------- Accuracy ----------------
with tab_accuracy:
    st.subheader("Models against the baselines (walk-forward test on 2025-2026)")
    st.write(
        "Each phase from 2025 on was predicted using **only earlier phases**, the way a real forecast "
        "would be made. **MAE** = the average miss in percentage points (lower is better). "
        "'Hard rows' leave out the easy cases where an agent had 0% last time and 0% again "
        f"({1 - backtest[(backtest['model'] == best)].eval('pick_rate == 0 and prev_pick_rate == 0').mean():.0%} "
        "of rows are hard)."
    )
    table = scores.assign(model=scores["model"].map(MODEL_LABELS))[
        ["model", "mae", "mae_nontrivial", "coverage", "width", "phases_won", "phases"]].rename(columns={
            "model": "Model", "mae": "MAE (all rows)", "mae_nontrivial": "MAE (hard rows)",
            "coverage": "80% range coverage", "width": "Range width (pts)",
            "phases_won": "Phases beating baseline", "phases": "Test phases"})
    st.dataframe(table.style.format({"MAE (all rows)": "{:.2f}", "MAE (hard rows)": "{:.2f}",
                                     "80% range coverage": "{:.0%}", "Range width (pts)": "{:.1f}"}),
                 hide_index=True, width="stretch")
    gain = s.loc[base, "mae"] - s.loc[best, "mae"]
    st.info(
        f"**Honest reading:** the best model improves on '{MODEL_LABELS[base]}' by only "
        f"{gain:.2f} percentage points and wins {int(s.loc[best, 'phases_won'])} of "
        f"{int(s.loc[best, 'phases'])} test phases. That is roughly a tie: with the features available "
        "so far (previous pick rate, rolling average, role, map), the last event is almost as good a "
        "guess as any model. Release dates and patch changes are not in the model yet."
    )
    phase_chart = by_phase.assign(test_phase=by_phase["year"].astype(str) + " phase " + by_phase["phase"].astype(str))
    st.altair_chart(
        alt.Chart(phase_chart).mark_line(point=True).encode(
            x=alt.X("test_phase:N", title="Test phase", sort=None),
            y=alt.Y("mae:Q", title="MAE (percentage points)"),
            color=alt.Color("model_label:N", title="Model"),
            tooltip=["model_label", "test_phase", alt.Tooltip("mae:Q", format=".2f"), "rows"],
        ).properties(height=360), width="stretch")
    with st.expander("What the linear regression learned"):
        st.write(
            "Prediction = intercept + each weight × its input. Role and map inputs are 1 if they apply, "
            "else 0. The model leans almost entirely on the previous pick rate and the rolling average."
        )
        st.dataframe(weights.assign(feature=weights["feature"].str.replace("categories__", "").str.replace("numbers__", "")),
                     hide_index=True)

# ---------------- Backtest explorer ----------------
with tab_backtest:
    st.subheader("Predicted vs actual, event by event")
    a, b, c = st.columns(3)
    agent = a.selectbox("Agent", sorted(backtest["agent"].unique()), index=sorted(backtest["agent"].unique()).index("Viper"))
    maps_for_agent = sorted(backtest.loc[backtest["agent"] == agent, "map_name"].unique())
    map_b = b.selectbox("Map ", maps_for_agent)
    model_b = c.selectbox("Model ", list(MODEL_LABELS), index=list(MODEL_LABELS).index(best),
                          format_func=MODEL_LABELS.get)
    h = backtest[(backtest["agent"] == agent) & (backtest["map_name"] == map_b) & (backtest["model"] == model_b)].copy()
    h["event_label"] = h["event"].str.replace("Champions Tour ", "").str.replace("Valorant ", "")
    order = list(h.sort_values(["year", "phase", "event"])["event_label"])
    x = alt.X("event_label:N", sort=order, title=None,
              axis=alt.Axis(labelAngle=-40, labelLimit=240, labelOverlap=False))
    band = alt.Chart(h).mark_bar(opacity=0.55, size=14, color="#8da4c4").encode(x=x, y=alt.Y("low:Q", title="Pick rate (%)",
                                                                             scale=alt.Scale(domain=[0, 100])), y2="high:Q")
    pred = alt.Chart(h).mark_point(shape="diamond", size=80, filled=True).encode(
        x=x, y="predicted:Q", tooltip=["event", alt.Tooltip("predicted:Q", format=".1f"),
                                       alt.Tooltip("low:Q", format=".1f"), alt.Tooltip("high:Q", format=".1f"),
                                       "pick_rate", "maps_played"])
    actual = alt.Chart(h).mark_point(color="#e8743b", size=60, filled=True).encode(x=x, y="pick_rate:Q")
    st.altair_chart((band + pred + actual).properties(height=380), width="stretch")
    st.caption("Diamond = prediction, blue bar = 80% range, orange dot = what actually happened. "
               "Small events (few maps played) are noisy, so big misses there are expected.")
    inside = h["pick_rate"].between(h["low"], h["high"]).mean() if len(h) else float("nan")
    st.write(f"{len(h)} test events for {agent} on {map_b}; actual value inside the range in {inside:.0%} of them.")

# ---------------- About ----------------
with tab_about:
    st.subheader("How it works")
    st.markdown(f"""
1. **Collect:** agent and map lists from valorant-api.com; pro pick rates from the Kaggle VCT dataset.
2. **Clean:** keep whole-event figures for the 49 top-tier events of 2023-2026, fix types, match names
   to IDs, and order events by season phase (Kickoff, Masters, Stage 1, Masters, Stage 2, Champions).
3. **Training table:** one row per agent, map and event. Inputs: the pick rate at the agent's last
   appearance on that map, and the average of its last 3 appearances, plus role and map. Built only
   from earlier phases.
4. **Walk-forward test:** predict each 2025-2026 phase using only earlier phases; score with MAE.
5. **80% range:** before each phase, the model predicts the phase before it; the 80th percentile of
   those misses becomes the ± margin (split conformal prediction). Coverage checks it's honest.

**Limitations:** pick rates at small events rest on few maps; the data stops in June 2026 (no Hush,
no Summit); release dates and patch notes are not yet in the model; the forecast assumes the next
event uses the same maps as Stage 1.
""")
