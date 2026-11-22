"""valreg: Valorant pro meta tracker and pick-rate forecast.

Reads only precomputed files in data/results/ (made by run_pipeline.py). No live fetching.

Run from the project folder:
    streamlit run app/streamlit_app.py
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

RESULTS = Path(__file__).resolve().parent.parent / "data" / "results"
RANGE_COLOR = "#8da4c4"
ACTUAL_COLOR = "#e8743b"

st.set_page_config(page_title="valreg: Valorant pro meta", layout="wide")


@st.cache_data
def load():
    files = ["next_phase_forecast", "phase_pick_rates", "agent_pick_rates", "agent_clusters",
             "backtest_predictions", "test_scores_by_phase", "model_scores"]
    return {f: pd.read_csv(RESULTS / f"{f}.csv") for f in files}


def short(name):
    """'Champions Tour 2024: Masters Shanghai' -> '2024 Masters Shanghai'; 'VCT 2025: Stage 1 (all regions)' -> '2025 Stage 1'."""
    s = name.replace(" (all regions)", "").replace("Champions Tour ", "").replace("VCT ", "").replace("Valorant ", "")
    if ": " in s:
        year, rest = s.split(": ", 1)
        return f"{year} {rest.replace(' / ' + year + ': ', ' / ')}"
    for y in ("2023", "2024", "2025", "2026"):
        if s.endswith(" " + y):
            return f"{y} {s[:-5]}"
    return s


d = load()
for key in ("phase_pick_rates", "agent_pick_rates", "backtest_predictions"):
    d[key]["phase_name"] = d[key]["phase_name"].map(short)
forecast, phases, agents_hist = d["next_phase_forecast"], d["phase_pick_rates"], d["agent_pick_rates"]
clusters, backtest, scores = d["agent_clusters"], d["backtest_predictions"], d["model_scores"]
chosen = scores[scores["chosen"]].iloc[0]
naive = scores.set_index("model").loc["same_as_last"]
latest_step = phases["step"].max()
latest_name = phases.loc[phases["step"] == latest_step, "phase_name"].iloc[0]
margin = forecast["margin"].iloc[0]

st.title("valreg: Valorant pro meta")
st.caption(
    "Pro pick rates from the Kaggle 'Valorant Champion Tour 2021-2026 Data' (scraped from vlr.gg), "
    f"data up to {latest_name} (dataset updated 2026-06-26). Agents and maps from valorant-api.com. "
    "Not affiliated with Riot Games."
)

c1, c2, c3, c4 = st.columns([1.5, 1, 1, 1])
c1.metric("Forecasting (2026)", "Masters London")
c2.metric("Margin of error (80%)", f"±{margin:.0f} pts")
c3.metric("Past forecasts inside their range", f"{chosen['test_coverage']:.0%}")
c4.metric("Pro phases analyzed (2023-26)", f"{phases['step'].nunique()}")

tab_fc, tab_trends, tab_styles, tab_acc = st.tabs(["Forecast", "Meta trends", "Playstyles", "Accuracy & method"])

# ---------------- Forecast ----------------
with tab_fc:
    st.subheader("Predicted pick rates for Masters London 2026")
    st.write(
        f"How often each agent is expected to be picked on each map, with an **80% range**: "
        f"forecasts made the same way for 2025-2026 events landed inside their range "
        f"{chosen['test_coverage']:.0%} of the time. The next event's map pool isn't in the data yet, "
        f"so these are the maps played in {latest_name}."
    )
    left, right = st.columns([1, 3])
    with left:
        map_name = st.selectbox("Map", sorted(forecast["map_name"].unique()))
        top_n = st.slider("Agents shown", 5, 30, 12)
        role_filter = st.multiselect("Roles", sorted(forecast["role"].unique()), default=sorted(forecast["role"].unique()))
    f = (forecast[(forecast["map_name"] == map_name) & forecast["role"].isin(role_filter)]
         .sort_values("predicted", ascending=False).head(top_n))
    with right:
        y = alt.Y("agent:N", sort=list(f["agent"]), title=None)
        tip = ["agent", "role", alt.Tooltip("predicted:Q", title="forecast %", format=".1f"),
               alt.Tooltip("low:Q", title="80% low", format=".1f"), alt.Tooltip("high:Q", title="80% high", format=".1f"),
               alt.Tooltip("prev_pick_rate:Q", title="last phase %", format=".1f")]
        bars = alt.Chart(f).mark_rule(strokeWidth=9, opacity=0.6, color=RANGE_COLOR).encode(
            y=y, x=alt.X("low:Q", title="Pick rate (%)", scale=alt.Scale(domain=[0, 100])), x2="high:Q", tooltip=tip)
        dots = alt.Chart(f).mark_point(filled=True, size=100, opacity=1).encode(y=y, x="predicted:Q", color="role:N", tooltip=tip)
        last = alt.Chart(f).mark_tick(color="gray", thickness=2, size=16).encode(y=y, x="prev_pick_rate:Q")
        st.altair_chart((bars + dots + last).properties(height=30 * max(len(f), 1) + 40), width="stretch")
        st.caption("Dot = forecast · blue bar = 80% range · grey tick = pick rate last phase.")

    st.subheader("Biggest expected changes")
    moves = forecast.assign(change=forecast["predicted"] - forecast["prev_pick_rate"])
    up, down = st.columns(2)
    cols = {"agent": "Agent", "map_name": "Map", "prev_pick_rate": "Last phase (%)", "predicted": "Forecast (%)",
            "change": "Change (pts)"}
    up.write("**Expected to rise**")
    up.dataframe(moves.nlargest(8, "change")[list(cols)].rename(columns=cols).round(1), hide_index=True, width="stretch")
    down.write("**Expected to fall**")
    down.dataframe(moves.nsmallest(8, "change")[list(cols)].rename(columns=cols).round(1), hide_index=True, width="stretch")
    st.caption("Forecasts lean toward the agent's recent average, so these are mostly agents expected to drift back "
               "after an unusually high or low phase, not predictions of patch changes.")

# ---------------- Meta trends ----------------
with tab_trends:
    st.subheader("Agent popularity across pro phases, 2023-2026")
    st.write("Pick rate across all maps, with every event in a phase combined (weighted by maps played).")
    order = list(agents_hist.drop_duplicates("step").sort_values("step")["phase_name"])
    latest_top = (agents_hist[agents_hist["step"] == agents_hist["step"].max()]
                  .nlargest(5, "pick_rate")["agent"].tolist())
    chosen_agents = st.multiselect("Agents", sorted(agents_hist["agent"].unique()), default=latest_top)
    a = agents_hist[agents_hist["agent"].isin(chosen_agents)]
    st.altair_chart(alt.Chart(a).mark_line(point=True).encode(
        x=alt.X("phase_name:N", sort=order, title=None,
                axis=alt.Axis(labelAngle=-40, labelLimit=260, labelOverlap=False)),
        y=alt.Y("pick_rate:Q", title="Pick rate (%)", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("agent:N", title="Agent"),
        tooltip=["agent", "phase_name", alt.Tooltip("pick_rate:Q", format=".1f"), "maps_played"],
    ).properties(height=420), width="stretch")

    st.subheader(f"Most picked agents per map in {latest_name}")
    m = st.selectbox("Map ", sorted(phases.loc[phases["step"] == latest_step, "map_name"].unique()))
    top = phases[(phases["step"] == latest_step) & (phases["map_name"] == m)].nlargest(10, "pick_rate")
    st.altair_chart(alt.Chart(top).mark_bar().encode(
        y=alt.Y("agent:N", sort="-x", title=None), x=alt.X("pick_rate:Q", title="Pick rate (%)", scale=alt.Scale(domain=[0, 100])),
        color="role:N", tooltip=["agent", "role", alt.Tooltip("pick_rate:Q", format=".1f"), "maps_played"],
    ).properties(height=320), width="stretch")
    st.caption(f"Based on {int(top['maps_played'].max()) if len(top) else 0} maps of {m} played in that phase.")

# ---------------- Playstyles ----------------
with tab_styles:
    st.subheader("Agent playstyle groups")
    st.write(
        "Agents grouped by what their abilities do (flash, smoke, recon, healing, mobility, traps, walls, "
        "crowd control), using k-means clustering. **First draft:** traits come from keywords in the "
        "official ability descriptions, so some tags are off, and the groups overlap a lot."
    )
    latest_overall = agents_hist[agents_hist["step"] == agents_hist["step"].max()][["agent", "pick_rate"]]
    cl = clusters.merge(latest_overall, on="agent", how="left").fillna({"pick_rate": 0})
    groups = sorted(cl["cluster"].unique())
    cols_ = st.columns(len(groups))
    for col, g in zip(cols_, groups):
        members = cl[cl["cluster"] == g].sort_values("pick_rate", ascending=False)
        col.markdown(f"**{g}**")
        col.dataframe(members[["agent", "pick_rate"]].rename(
            columns={"agent": "Agent", "pick_rate": "Pick %"}).round(0),
            hide_index=True, width="stretch")
    st.caption(f"Pick % = pick rate across all maps in {latest_name}.")
    with st.expander("Traits per agent"):
        st.dataframe(cl[["agent", "role", "cluster", "traits"]], hide_index=True, width="stretch")

# ---------------- Accuracy & method ----------------
with tab_acc:
    st.subheader("How accurate are the forecasts?")
    st.write(
        f"Every 2025-2026 phase was forecast using **only earlier data**, exactly as the Masters London forecast "
        f"was made. On average a forecast missed by **{chosen['test_mae']:.1f} percentage points**, and "
        f"**{chosen['test_coverage']:.0%}** of real values landed inside the 80% range."
    )
    st.info(
        f"**Honest context:** simply assuming each agent keeps last phase's pick rate misses by "
        f"{naive['test_mae']:.1f} points. The forecast is only slightly better than that "
        f"({naive['test_mae'] - chosen['test_mae']:.2f} points), so the pro meta is largely 'like last time, "
        "drifting back toward normal'. Patch changes, which likely drive the big shifts, aren't in the data yet."
    )
    a1, a2, a3 = st.columns(3)
    agent = a1.selectbox("Agent ", sorted(backtest["agent"].unique()), index=sorted(backtest["agent"].unique()).index("Viper"))
    maps_for = sorted(backtest.loc[backtest["agent"] == agent, "map_name"].unique())
    map_b = a2.selectbox("Map  ", maps_for, index=maps_for.index("Split") if "Split" in maps_for else 0)
    h = backtest[(backtest["agent"] == agent) & (backtest["map_name"] == map_b)].sort_values("step")
    x = alt.X("phase_name:N", sort=list(h["phase_name"]), title=None,
              axis=alt.Axis(labelAngle=-40, labelLimit=260, labelOverlap=False))
    band = alt.Chart(h).mark_bar(opacity=0.55, size=16, color=RANGE_COLOR).encode(
        x=x, y=alt.Y("low:Q", title="Pick rate (%)", scale=alt.Scale(domain=[0, 100])), y2="high:Q")
    pred = alt.Chart(h).mark_point(shape="diamond", size=90, filled=True).encode(
        x=x, y="predicted:Q", tooltip=["phase_name", alt.Tooltip("predicted:Q", format=".1f"),
                                       alt.Tooltip("pick_rate:Q", title="actual", format=".1f"), "maps_played"])
    actual = alt.Chart(h).mark_point(color=ACTUAL_COLOR, size=70, filled=True).encode(x=x, y="pick_rate:Q")
    st.altair_chart((band + pred + actual).properties(height=380), width="stretch")
    inside = h["pick_rate"].between(h["low"], h["high"]).mean() if len(h) else float("nan")
    st.caption(f"Diamond = forecast · blue bar = 80% range · orange dot = what happened. "
               f"{agent} on {map_b}: inside the range in {inside:.0%} of {len(h)} phases.")

    st.subheader("How it works")
    st.markdown("""
1. **Collect:** agent and map lists from valorant-api.com; pro pick rates from the Kaggle VCT dataset;
   season order and event dates entered by hand (dates from Wikipedia).
2. **Clean:** keep whole-event figures for the 49 top-tier events of 2023-2026, fix types, match names
   to IDs, and order events by season phase (Kickoff, Masters, Stage 1, Masters, Stage 2, Champions).
3. **Combine:** each phase's events are merged per agent and map, weighted by maps played.
4. **Forecast:** a median linear regression predicts next phase's pick rate from last phase's pick rate,
   the average of the last 3 appearances, role and map. It was chosen over other models by testing on
   2024 only, then checked once on 2025-2026.
5. **Margin of error:** the 80th percentile of the forecast's misses over the previous 3 phases.

**Limitations:** single-region pick rates rest on few maps and are noisy; the data stops in June 2026
(no Hush, no Summit); patch changes aren't modeled; the next event's map pool is assumed to match Stage 1;
Reddit, vlr.gg and Riot's sites weren't used because their terms don't allow automated collection.
""")
