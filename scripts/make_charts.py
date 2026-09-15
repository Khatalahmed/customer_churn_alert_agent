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

fig, ax = plt.subplots(figsize=(7.4, 3.6))
ax.barh(names, vals, color="#4f46e5")
ax.set_title("What the churn model relies on  (XGBoost, leakage-safe features)",
             fontweight="bold", loc="left")
ax.set_xlabel("feature importance")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig("docs/img/feature_importance.png", dpi=140, bbox_inches="tight")
plt.close(fig)

# --------------------------------------------------------------------------- #
# 2. Per-archetype: recall (churners) vs false-alarm (traps)
#    Out-of-fold values (5-fold CV, mean over 10 fold seeds) from
#    churn.archetype_eval - NOT the in-sample numbers of the saved model.
# --------------------------------------------------------------------------- #
labels = ["cliff-dropper\n(churner)", "gradual-fader\n(churner)",
          "vacationer\n(trap)", "loyal buyer\n(trap)", "regular\nactive"]
rates = [42, 61, 42, 36, 15]
colors = ["#16a34a", "#16a34a", "#dc2626", "#dc2626", "#94a3b8"]

fig, ax = plt.subplots(figsize=(7.4, 3.8))
bars = ax.bar(labels, rates, color=colors, width=0.62)
ax.set_ylabel("% flagged by the model")
ax.set_ylim(0, 100)
ax.set_title("Per-archetype flag rate  (out-of-fold, threshold 0.5)",
             fontweight="bold", loc="left")
for b, r in zip(bars, rates):
    ax.text(b.get_x() + b.get_width() / 2, r + 2, f"{r}%",
            ha="center", fontweight="bold", fontsize=10)
ax.axhline(50, color="#e5e7eb", lw=1, zorder=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.text(0.01, -0.02,
         "green = recall on real churners   •   red = false-alarm on look-alike traps   "
         "•   grey = false-alarm on regular customers",
         fontsize=9, color="#6b7280")
fig.tight_layout()
fig.savefig("docs/img/archetype_recall.png", dpi=140, bbox_inches="tight")
plt.close(fig)

print("Wrote docs/img/feature_importance.png and docs/img/archetype_recall.png")
