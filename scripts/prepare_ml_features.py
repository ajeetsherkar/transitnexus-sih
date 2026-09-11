import json
from pathlib import Path

import pandas as pd

INPUT = Path("data/processed/events.json")
OUTPUT = Path("data/processed/ml/ml_features.csv")

# Load events
events = json.loads(INPUT.read_text())
df = pd.DataFrame(events)

# Parse timestamp
df["timestamp"] = pd.to_datetime(df["timestamp"], format="mixed", utc=True)

# Time-of-day features
df["hour"] = df["timestamp"].dt.hour
df["minute"] = df["timestamp"].dt.minute
df["time_of_day"] = pd.cut(
    df["hour"],
    bins=[-1, 6, 12, 18, 24],
    labels=["night", "morning", "afternoon", "evening"]
)

# Create spatial zones using rounded GPS coordinates
df["zone_lat"] = df["lat"].round(3)
df["zone_lon"] = df["lon"].round(3)
df["zone"] = (
    df["zone_lat"].astype(str) + "_" + df["zone_lon"].astype(str)
)

# Create 10-second time windows
df["time_window"] = df["timestamp"].dt.floor("10s")

# Group by spatial zone + time window
group_cols = ["zone", "zone_lat", "zone_lon", "time_window"]

group = df.groupby(group_cols, observed=True)

features = group.size().reset_index(name="event_count")

# Event-type counts
for event_type, column in [
    ("pothole", "pothole_count"),
    ("congestion", "congestion_count"),
    ("pedestrian_risk", "pedestrian_risk_count"),
]:
    counts = (
        df[df["event_type"] == event_type]
        .groupby(group_cols, observed=True)
        .size()
        .reset_index(name=column)
    )
    features = features.merge(
        counts,
        on=group_cols,
        how="left"
    )

# Fill missing event-type counts with zero
for column in [
    "pothole_count",
    "congestion_count",
    "pedestrian_risk_count",
]:
    features[column] = features[column].fillna(0)

# Event-type mix ratios
features["pothole_ratio"] = (
    features["pothole_count"] / features["event_count"]
)

features["congestion_ratio"] = (
    features["congestion_count"] / features["event_count"]
)

features["pedestrian_risk_ratio"] = (
    features["pedestrian_risk_count"] / features["event_count"]
)

# Density score = events observed in this zone/time window
features["density_score"] = features["event_count"]

# Time features
features["hour"] = features["time_window"].dt.hour
features["minute"] = features["time_window"].dt.minute

features["time_of_day"] = pd.cut(
    features["hour"],
    bins=[-1, 6, 12, 18, 24],
    labels=["night", "morning", "afternoon", "evening"]
)

# Save
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
features.to_csv(OUTPUT, index=False)

print("Feature engineering complete.")
print("Input events:", len(df))
print("Feature rows:", len(features))
print("Zones:", features["zone"].nunique())
print("Time windows:", features["time_window"].nunique())
print("\nFeature columns:")
print(features.columns.tolist())
print("\nDensity statistics:")
print(features["density_score"].describe().to_string())
print("\nSample features:")
print(features.head(10).to_string(index=False))
print("\nSaved to:", OUTPUT)
