"""
archetype_eval.py

WHAT : Measures the model's churn recall PER ARCHETYPE, and the false-alarm
       rate on the two "trap" archetypes (vacationer, loyal bulk-buyer).
WHY  : A single recall number hides WHERE the model struggles. Per-archetype
       recall shows it catches sudden cliff-droppers easily but slow faders
       less well - and whether it wrongly flags customers who only LOOK
       dormant (vacationers, loyal low-frequency buyers).
FLOW : load answer key (archetype + churned) -> 5-fold cross-validation:
       each customer is scored by a model trained on the OTHER 4 folds ->
       flag if churn_probability > threshold -> group by archetype -> print
       recall (churned types) and false-alarm rate (traps).
LOGIC: scoring with the saved churn_model.pkl would be in-sample (it trained
       on 75% of these customers) and flatter the numbers. Out-of-fold
       predictions give every customer an honest score while still using all
       300, which matters because the trap archetypes are small. The
       in-sample rate is printed alongside to show the gap.
"""
import json

import joblib
import numpy as np
from sklearn.model_selection import StratifiedKFold

from .config import MODEL_PATH, TRUTH_PATH
from .features import add_labels, build_features
from .train_model import make_model

THRESHOLD = 0.5
N_FOLDS = 5
ORDER = ["cliff_dropper", "gradual_fader", "vacationer", "loyal_bulk_buyer", "regular_active"]
CHURNED_TYPES = {"cliff_dropper", "gradual_fader"}


def oof_probabilities(X, y, n_folds: int = N_FOLDS, seed: int = 42) -> np.ndarray:
    """Churn probability for every row, each from a model that never saw that row."""
    oof = np.zeros(len(X))
    folds = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=seed)
    for train_idx, test_idx in folds.split(X, y):
        model = make_model(y.iloc[train_idx])
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        oof[test_idx] = model.predict_proba(X.iloc[test_idx])[:, 1]
    return oof


def main():
    df, cols = build_features()
    df = add_labels(df)
    X, y = df[cols], df["churned"]

    # --- honest: out-of-fold probabilities ---
    oof = oof_probabilities(X, y)
    flagged_oof = set(df.loc[oof > THRESHOLD, "user_id"])

    # --- for comparison: the saved model, which saw most of these customers ---
    saved = joblib.load(MODEL_PATH)
    in_sample = saved["model"].predict_proba(X[saved["features"]])[:, 1]
    flagged_in = set(df.loc[in_sample > THRESHOLD, "user_id"])

    with open(TRUTH_PATH) as f:
        truth = json.load(f)

    by_arch = {}
    for r in truth:
        by_arch.setdefault(r["archetype"], []).append(r["user_id"])

    print("=" * 76)
    print(f"PER-ARCHETYPE MODEL PERFORMANCE  (flag if churn prob > {THRESHOLD}, "
          f"{N_FOLDS}-fold out-of-fold)")
    print("=" * 76)
    print(f"{'archetype':<20}{'churned?':<12}{'n':>4}{'flagged':>9}{'rate':>7}"
          f"{'in-sample':>11}")
    print("-" * 76)

    for arch in ORDER:
        ids = by_arch.get(arch, [])
        if not ids:
            continue
        n = len(ids)
        hit = sum(1 for uid in ids if uid in flagged_oof)
        hit_in = sum(1 for uid in ids if uid in flagged_in)
        if arch in CHURNED_TYPES:
            churned_label, meaning = "yes", "recall"
        elif arch == "regular_active":
            churned_label, meaning = "no", "false-alarm"
        else:
            churned_label, meaning = "NO (trap)", "false-alarm"
        print(f"{arch:<20}{churned_label:<12}{n:>4}{hit:>9}{hit / n:>7.0%}"
              f"{hit_in / n:>11.0%}  ({meaning})")
    print("=" * 76)
    print("rate = honest (each customer scored by a model that never saw them)")
    print("in-sample = saved churn_model.pkl on all customers (optimistic, for contrast)")


if __name__ == "__main__":
    main()
