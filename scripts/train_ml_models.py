from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.metrics import classification_report, mean_squared_error
from sklearn.model_selection import train_test_split


DATA_PATH = Path("data/processed/ml/ml_features.csv")
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Load engineered features
df = pd.read_csv(DATA_PATH)

# ---------------------------------------------------------
# 1. Congestion severity label
# ---------------------------------------------------------
# Use the actual density distribution to define three classes.
low_threshold = df["density_score"].quantile(1 / 3)
high_threshold = df["density_score"].quantile(2 / 3)

def severity(density):
    if density <= low_threshold:
        return "low"
    elif density <= high_threshold:
        return "medium"
    return "high"

df["congestion_severity"] = df["density_score"].apply(severity)

# ---------------------------------------------------------
# 2. Random Forest congestion classifier
# ---------------------------------------------------------
classification_features = [
    "density_score",
    "event_count",
    "pothole_ratio",
    "congestion_ratio",
    "pedestrian_risk_ratio",
    "zone_lat",
    "zone_lon",
    "hour",
    "minute",
]

X_cls = df[classification_features]
y_cls = df["congestion_severity"]

X_train_cls, X_test_cls, y_train_cls, y_test_cls = train_test_split(
    X_cls,
    y_cls,
    test_size=0.25,
    random_state=42,
    stratify=y_cls,
)

rf_model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    class_weight="balanced",
)

rf_model.fit(X_train_cls, y_train_cls)
y_pred_cls = rf_model.predict(X_test_cls)

# ---------------------------------------------------------
# 3. Simulated route-delay target
# ---------------------------------------------------------
# This is a prototype target derived from observed density
# and event counts. It is NOT real traffic-delay ground truth.
df["delay_minutes"] = (
    2.0
    + 0.08 * df["density_score"]
    + 0.03 * df["event_count"]
    + 3.0 * df["congestion_count"]
    + 1.5 * df["pedestrian_risk_count"]
    + np.random.default_rng(42).normal(0, 0.5, len(df))
)

regression_features = [
    "density_score",
    "event_count",
    "pothole_ratio",
    "congestion_ratio",
    "pedestrian_risk_ratio",
    "zone_lat",
    "zone_lon",
    "hour",
    "minute",
]

X_reg = df[regression_features]
y_reg = df["delay_minutes"]

X_train_reg, X_test_reg, y_train_reg, y_test_reg = train_test_split(
    X_reg,
    y_reg,
    test_size=0.25,
    random_state=42,
)

gbr_model = GradientBoostingRegressor(
    n_estimators=150,
    learning_rate=0.05,
    max_depth=2,
    random_state=42,
)

gbr_model.fit(X_train_reg, y_train_reg)
y_pred_reg = gbr_model.predict(X_test_reg)

rmse = mean_squared_error(y_test_reg, y_pred_reg) ** 0.5

# ---------------------------------------------------------
# 4. Save models
# ---------------------------------------------------------
rf_path = MODEL_DIR / "congestion_rf.joblib"
gbr_path = MODEL_DIR / "route_delay_gbr.joblib"

joblib.dump(rf_model, rf_path)
joblib.dump(gbr_model, gbr_path)

# ---------------------------------------------------------
# 5. Report results
# ---------------------------------------------------------
print("=" * 60)
print("TRANSITNEXUS — SESSION 1 ML TRAINING")
print("=" * 60)

print("\nCongestion severity thresholds:")
print(f"Low <= {low_threshold:.2f}")
print(f"Medium <= {high_threshold:.2f}")
print(f"High  > {high_threshold:.2f}")

print("\nClass distribution:")
print(df["congestion_severity"].value_counts().to_string())

print("\nRandom Forest classification report:")
print(classification_report(y_test_cls, y_pred_cls, zero_division=0))

print(f"Gradient Boosting RMSE: {rmse:.4f} minutes")

print("\nModel files:")
print(f"Random Forest: {rf_path}")
print(f"Gradient Boosting: {gbr_path}")

print("\nTraining samples:")
print(f"Classifier train/test: {len(X_train_cls)}/{len(X_test_cls)}")
print(f"Regressor train/test:   {len(X_train_reg)}/{len(X_test_reg)}")

print("\nNOTE:")
print("The GBR delay target is simulated from observed event density/counts")
print("for prototype/Q&A purposes; it is not real traffic-delay ground truth.")
