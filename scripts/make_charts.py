"""
make_charts.py

Generates the PNG charts embedded in the README (docs/img/).
Standalone: loads churn_model.pkl directly, no churn-package import needed.

    uv run python scripts/make_charts.py
"""
import os

import joblib
import matplotlib

matplotlib.use("Agg")  # no display needed
import matplotlib.pyplot as plt

os.makedirs("docs/img", exist_ok=True)

INK = "#111827"
plt.rcParams.update({
    "font.size": 11,
    "axes.edgecolor": "#e5e7eb",
    "axes.linewidth": 1,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": INK,
    "ytick.color": INK,
})

# --------------------------------------------------------------------------- #
# 1. XGBoost feature importance
# --------------------------------------------------------------------------- #
bundle = joblib.load("churn_model.pkl")
model, cols = bundle["model"], bundle["features"]
pairs = sorted(zip(cols, model.feature_importances_), key=lambda x: x[1])
names = [c.replace("_", " ") for c, _ in pairs]
vals = [float(v) for _, v in pairs]

fig, ax = plt.subplots(figsize=(7.4, 4.2))
ax.barh(names, vals, color="#4f46e5")
ax.set_title("What the churn model relies on  (point-in-time features)",
             fontweight="bold", loc="left")
ax.set_xlabel("feature importance")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig("docs/img/feature_importance.png", dpi=140, bbox_inches="tight")
plt.close(fig)

# --------------------------------------------------------------------------- #
# 2. Precision of the top 15 vs picking at random (held-out snapshot)
#    Values from churn.train_model / the precision@k check and churn.eval.
#    AGENT_PRECISION is from a live LLM run (None = not measured -> bar omitted).
# --------------------------------------------------------------------------- #
BASE_RATE = 0.014
AGENT_PRECISION = None      # stale: the last agent run predates this dataset

bars_spec = [
    ("pick at\nrandom", BASE_RATE, "#94a3b8"),
    ('"no orders\nin 14 days"', 0.00, "#dc2626"),
    ("logistic\nregression", 0.07, "#4f46e5"),
    ("XGBoost\n(this project)", 0.13, "#16a34a"),
]
if AGENT_PRECISION is not None:
    bars_spec.append(("agent verdicts\n(HIGH + MEDIUM)", AGENT_PRECISION, "#16a34a"))

fig, ax = plt.subplots(figsize=(7.4, 3.8))
labels = [b[0] for b in bars_spec]
values = [b[1] * 100 for b in bars_spec]
bars = ax.bar(labels, values, color=[b[2] for b in bars_spec], width=0.6)
ax.set_ylabel("% that really churned")
ax.set_ylim(0, 30)
ax.set_title("Who actually churns in the next 14 days?  (held-out snapshot)",
             fontweight="bold", loc="left")
for b, v in zip(bars, values):
    ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.0f}%",
            ha="center", fontweight="bold", fontsize=10)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.text(0.01, -0.02,
         "2,487 active customers, 35 churn in the next 14 days  -  model never saw this snapshot",
         fontsize=9, color="#6b7280")
fig.tight_layout()
fig.savefig("docs/img/precision_at_15.png", dpi=140, bbox_inches="tight")
plt.close(fig)

print("Wrote docs/img/feature_importance.png and docs/img/precision_at_15.png")
