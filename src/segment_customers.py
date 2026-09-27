"""Customer segmentation with K-Means on RFM features, plus the charts for the README.

Usage (from the repo root, after `python src/run_sql.py`):
    python src/segment_customers.py

Steps
    1. Load the per-customer RFM table produced by sql/04_rfm.sql.
    2. Log-transform (RFM is heavily right-skewed) and standardise the three features.
    3. Try k = 2..8, record inertia (elbow) and silhouette score.
    4. Fit the chosen k, name each cluster from its profile, and size each segment's
       share of customers and revenue.
    5. Cross-check the clusters against the rule-based RFM segments from SQL.
    6. Save tables to outputs/ and charts to outputs/charts/.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
CHARTS = OUT / "charts"
FEATURES = ["recency_days", "frequency", "monetary"]
CHOSEN_K = 4          # see README: silhouette ~tied with k=3, elbow flattens, k=4 is more actionable
RANDOM_STATE = 42

# Chart styling: one blue for single series, fixed categorical order for two series.
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"
plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.8, "figure.dpi": 150, "savefig.bbox": "tight",
})


def name_segment(row: pd.Series, med: pd.Series) -> str:
    """Name a cluster from its median profile relative to the whole customer base."""
    recent = row.recency_days <= med.recency_days
    frequent = row.frequency > med.frequency
    if recent and row.frequency >= 3 * med.frequency:
        return "Champions"
    if frequent:
        return "Cooling Regulars"
    if recent:
        return "New / Low-Frequency"
    return "Lapsed One-Timers"


def main() -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    rfm = pd.read_csv(OUT / "rfm.csv")
    X = StandardScaler().fit_transform(np.log1p(rfm[FEATURES]))

    # --- choose k -------------------------------------------------------------
    rows = []
    for k in range(2, 9):
        km = KMeans(n_clusters=k, n_init=20, random_state=RANDOM_STATE).fit(X)
        rows.append({"k": k, "inertia": round(km.inertia_, 1),
                     "silhouette": round(silhouette_score(X, km.labels_), 3)})
    k_eval = pd.DataFrame(rows)
    k_eval.to_csv(OUT / "k_selection.csv", index=False)
    print(k_eval.to_string(index=False))

    # --- fit chosen k, name clusters, profile ---------------------------------
    km = KMeans(n_clusters=CHOSEN_K, n_init=20, random_state=RANDOM_STATE).fit(X)
    rfm["cluster"] = km.labels_
    overall_median = rfm[FEATURES].median()
    id_to_name = {cid: name_segment(grp[FEATURES].median(), overall_median)
                  for cid, grp in rfm.groupby("cluster")}
    assert len(set(id_to_name.values())) == CHOSEN_K, f"segment names collided: {id_to_name}"
    rfm["segment"] = rfm.cluster.map(id_to_name)

    profile = rfm.groupby("segment").agg(
        customers=("customer_id", "count"),
        median_recency_days=("recency_days", "median"),
        median_orders=("frequency", "median"),
        median_spend_gbp=("monetary", "median"),
        revenue_gbp=("monetary", "sum"),
    )
    profile["customer_share_pct"] = (100 * profile.customers / profile.customers.sum()).round(1)
    profile["revenue_share_pct"] = (100 * profile.revenue_gbp / profile.revenue_gbp.sum()).round(1)
    profile["revenue_gbp"] = profile.revenue_gbp.round(0)
    profile["median_spend_gbp"] = profile.median_spend_gbp.round(2)
    profile = profile.sort_values("revenue_gbp", ascending=False)
    profile.to_csv(OUT / "segment_profile.csv")
    print(profile.to_string())

    rfm[["customer_id", *FEATURES, "rfm_segment", "segment"]].to_csv(
        OUT / "customer_segments.csv", index=False)

    # --- cross-check against rule-based RFM segments --------------------------
    xtab = pd.crosstab(rfm.segment, rfm.rfm_segment)
    xtab.to_csv(OUT / "kmeans_vs_rfm_rules.csv")
    print(xtab.to_string())

    make_charts(k_eval, profile)


def make_charts(k_eval: pd.DataFrame, profile: pd.DataFrame) -> None:
    # 1. Monthly revenue (Dec 2011 is a partial month: data ends 9 Dec)
    m = pd.read_csv(OUT / "monthly_revenue.csv", parse_dates=["month"])
    m = m[m.month < "2011-12-01"]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.plot(m.month, m.revenue_gbp / 1e3, color=BLUE, lw=2, marker="o", ms=4)
    ax.set_title("Monthly revenue, Dec 2010 - Nov 2011", loc="left")
    ax.set_ylabel("Revenue (GBP thousands)")
    ax.set_ylim(0, None)
    peak = m.loc[m.revenue_gbp.idxmax()]
    ax.annotate(f"Peak: GBP {peak.revenue_gbp/1e3:,.0f}K ({peak.month:%b %Y})",
                (peak.month, peak.revenue_gbp / 1e3), xytext=(-150, -8),
                textcoords="offset points", color=INK_2, fontsize=9)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %y"))
    fig.savefig(CHARTS / "monthly_revenue.png"); plt.close(fig)

    # 2. Cohort retention heatmap (single-hue sequential)
    c = pd.read_csv(OUT / "cohort_retention.csv", parse_dates=["cohort_month"])
    piv = c.pivot(index="cohort_month", columns="month_index", values="retention_pct")
    piv = piv.drop(columns=0).dropna(how="all")  # Nov 2011 cohort has no follow-up month yet
    sizes = c[c.month_index == 0].set_index("cohort_month").cohort_size
    fig, ax = plt.subplots(figsize=(9, 4.8))
    im = ax.imshow(piv.values, cmap="Blues", vmin=0, vmax=50, aspect="auto")
    ax.set_xticks(range(piv.shape[1]), [f"M+{i}" for i in piv.columns])
    ax.set_yticks(range(piv.shape[0]), [f"{d:%b %Y} (n={sizes[d]})" for d in piv.index])
    ax.grid(False)
    for (i, j), v in np.ndenumerate(piv.values):
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8,
                    color="white" if v > 28 else INK)
    ax.set_title("Cohort retention: % of each first-order cohort ordering again", loc="left")
    ax.set_xlabel("Months after first order")
    fig.colorbar(im, ax=ax, label="Retention %", shrink=0.8)
    fig.savefig(CHARTS / "cohort_retention.png"); plt.close(fig)

    # 3. Choosing k: elbow and silhouette as two panels (never a dual axis)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9, 3.3))
    for ax, col, title in [(a1, "inertia", "Elbow: within-cluster SSE"),
                           (a2, "silhouette", "Silhouette score (higher = better)")]:
        ax.plot(k_eval.k, k_eval[col], color=BLUE, lw=2, marker="o", ms=5)
        ax.axvline(CHOSEN_K, color=INK_2, lw=1, ls="--")
        ax.set_title(title, loc="left", fontsize=11)
        ax.set_xlabel("Number of clusters (k)")
    a1.text(CHOSEN_K + 0.1, a1.get_ylim()[1] * 0.9, f"chosen k={CHOSEN_K}", color=INK_2, fontsize=9)
    fig.savefig(CHARTS / "choosing_k.png"); plt.close(fig)

    # 4. Segment share of customers vs revenue
    p = profile.iloc[::-1]
    y = np.arange(len(p)); h = 0.38
    fig, ax = plt.subplots(figsize=(8, 3.6))
    b1 = ax.barh(y + h / 2, p.customer_share_pct, h - 0.04, color=BLUE, label="% of customers")
    b2 = ax.barh(y - h / 2, p.revenue_share_pct, h - 0.04, color=ORANGE, label="% of revenue")
    for bars in (b1, b2):
        ax.bar_label(bars, fmt="%.1f%%", padding=3, fontsize=8, color=INK_2)
    ax.set_yticks(y, p.index)
    ax.set_xlabel("Share (%)"); ax.grid(axis="y", visible=False)
    ax.set_title("Customer segments: share of customers vs share of revenue", loc="left")
    ax.legend(frameon=False, loc="lower right")
    fig.savefig(CHARTS / "segment_share.png"); plt.close(fig)


if __name__ == "__main__":
    main()
