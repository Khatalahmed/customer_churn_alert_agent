"""
train_model.py

WHAT : Trains an XGBoost model to predict churn from the leakage-safe
       features, then reports honest metrics on a held-out test set.
WHY  : This is the ML core. The model scores every customer cheaply, so the
       agent only investigates the high-risk ones. We measure it on data it
       never saw during training (the test set), which is the honest way.
FLOW : build features -> split into train/test -> train XGBoost (with class
       weighting because churn is rare) -> score the test set -> print AUC,
       precision, recall, and which features matter most -> save the model.
LOGIC: churn is only ~23% of customers, so we set scale_pos_weight to stop
       the model from lazily predicting "everyone is fine".
"""
import joblib
from sklearn.metrics import (classification_report, confusion_matrix,
                             f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from features import build_features

df, cols = build_features()
X = df[cols]
y = df["churned"]

# split: model trains on 75%, is judged on the unseen 25%
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.25, random_state=42, stratify=y
)

# churn is rare -> weight the positive class so the model takes it seriously
pos = int(y_train.sum())
neg = len(y_train) - pos
scale = neg / pos

model = XGBClassifier(
    n_estimators=200,
    max_depth=3,
    learning_rate=0.08,
    subsample=0.9,
    colsample_bytree=0.9,
    scale_pos_weight=scale,
    eval_metric="logloss",
    random_state=42,
)
model.fit(X_train, y_train)

# score the unseen test set
proba = model.predict_proba(X_test)[:, 1]
pred = (proba >= 0.5).astype(int)

print("=" * 60)
print("XGBOOST CHURN MODEL - TEST SET RESULTS")
print("=" * 60)
print(f"Test customers: {len(y_test)}  (churned: {int(y_test.sum())})")
print(f"ROC-AUC:   {roc_auc_score(y_test, proba):.3f}")
print(f"Precision: {precision_score(y_test, pred):.3f}")
print(f"Recall:    {recall_score(y_test, pred):.3f}")
print(f"F1:        {f1_score(y_test, pred):.3f}")
print("\nConfusion matrix [rows=true, cols=pred]:")
print(confusion_matrix(y_test, pred))
print("\nClassification report:")
print(classification_report(y_test, pred, target_names=["active", "churned"]))

print("Feature importance (higher = more useful to the model):")
for name, imp in sorted(zip(cols, model.feature_importances_), key=lambda x: -x[1]):
    print(f"  {name:<26} {imp:.3f}")

# save the model + the feature list so the scoring tool can reuse them
joblib.dump({"model": model, "features": cols}, "churn_model.pkl")
print("\nSaved model to churn_model.pkl")