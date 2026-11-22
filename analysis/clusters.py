"""Group agents into playstyles from their ability descriptions.

1. TAG: each agent gets traits from keywords in its ability descriptions
   (newest data/raw/agents_*.json from valorant-api.com). Example: an ability that
   "blinds" enemies -> flash. The keyword lists are in TRAITS; they're a transparent,
   first-draft tagging and worth checking by hand.
2. CLUSTER: k-means groups agents with similar trait sets. k (4 or 5) is chosen by the
   silhouette score (how well each agent fits its own group vs the next-closest group).
3. NAME: each group is named after the traits most common in it.

Output: data/results/agent_clusters.csv (one row per agent: cluster name and traits).

Run from the project folder:
    python analysis/clusters.py
"""

import json
import re
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
RESULTS_DIR = ROOT / "data" / "results"

# trait -> words that signal it in an ability description (matched as word starts)
TRAITS = {
    "flash": ["blind", "flash", "nearsight"],
    "smoke": ["smoke", "vision-block", "blocks vision", "obscur", "cloud"],
    "recon": ["reveal", "detect", "mark", "scan", "track"],
    "healing": ["heal", "revive", "resurrect", "restore"],
    "mobility": ["dash", "teleport", "propel", "leap", "jump", "fly", "airborne", "updraft", "boost"],
    "traps": ["trap", "tripwire", "alarm", "turret", "trip", "sensor", "camera"],
    "walls": ["wall", "barrier"],
    "crowd_control": ["slow", "concuss", "stun", "daze", "suppress", "tether"],
}
# Not used: "damage" (27 of 30 agents have a damaging ability, so it can't tell agents apart).


def load_agents():
    newest = sorted(RAW_DIR.glob("agents_*.json"))[-1]
    return json.loads(newest.read_text(encoding="utf-8"))["data"]


def tag(agent):
    """1/0 per trait: does any ability description contain one of its keywords?"""
    text = " ".join((a.get("description") or "") for a in agent["abilities"]).lower()
    return {t: int(any(re.search(r"\b" + re.escape(w), text) for w in words)) for t, words in TRAITS.items()}


def name_clusters(df, labels):
    """Name each cluster after its two most common traits (share of members having them)."""
    names = {}
    for c in sorted(set(labels)):
        share = df[labels == c][list(TRAITS)].mean().sort_values(ascending=False)
        top = [t.replace("_", " ") for t in share.index[:2] if share[t] >= 0.5]
        names[c] = " + ".join(top).title() if top else "Generalist"
    return names


if __name__ == "__main__":
    agents = load_agents()
    df = pd.DataFrame([{"agent": a["displayName"], "role": a["role"]["displayName"], **tag(a)} for a in agents])
    X = df[list(TRAITS)].to_numpy()

    best_k, best_score, best_labels = None, -1, None
    for k in (4, 5):
        labels = KMeans(n_clusters=k, n_init=50, random_state=0).fit_predict(X)
        s = silhouette_score(X, labels)
        print(f"k={k}: silhouette {s:.3f}")
        if s > best_score:
            best_k, best_score, best_labels = k, s, labels

    names = name_clusters(df, best_labels)
    df["cluster"] = [names[c] for c in best_labels]
    df["traits"] = df[list(TRAITS)].apply(lambda r: ", ".join(t.replace("_", " ") for t in TRAITS if r[t]), axis=1)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    df.sort_values(["cluster", "agent"]).to_csv(RESULTS_DIR / "agent_clusters.csv", index=False)

    print(f"\nChose k={best_k}")
    for c, g in df.groupby("cluster"):
        print(f"\n{c} ({len(g)}): " + ", ".join(f"{a} [{r}]" for a, r in zip(g["agent"], g["role"])))
    print("\nTrait counts:", df[list(TRAITS)].sum().to_dict())
