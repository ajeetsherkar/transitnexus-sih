import os
from collections import Counter

import folium
import pandas as pd
import requests
import streamlit as st
from folium.plugins import HeatMap
from streamlit_folium import st_folium


API_URL = os.getenv("TRANSITNEXUS_API_URL", "http://127.0.0.1:8000")

ROUTE_POINTS = [
    (19.884225, 74.478773),
    (19.886319, 74.479936),
    (19.888414, 74.481100),
    (19.890508, 74.482263),
    (19.893249, 74.484267),
    (19.895990, 74.486270),
    (19.898731, 74.488274),
    (19.901472, 74.490278),
    (19.902013, 74.493611),
    (19.902554, 74.496944),
    (19.903094, 74.500277),
    (19.903635, 74.503610),
]

EVENT_COLORS = {
    "pothole": "orange",
    "pedestrian_risk": "red",
    "congestion": "yellow",
    "car": "blue",
    "bus": "green",
    "truck": "purple",
    "motorcycle": "cadetblue",
    "bicycle": "lightgreen",
    "person": "darkred",
}

st.set_page_config(
    page_title="TransitNexus Urban Intelligence",
    page_icon="🚌",
    layout="wide",
)

st.title("TransitNexus Urban Intelligence")
st.caption("AI-powered mobile urban intelligence using public transport fleet data")

try:
    response = requests.get(f"{API_URL}/events", timeout=10)
    response.raise_for_status()
    events = response.json()
except requests.RequestException as exc:
    st.error(f"Unable to connect to TransitNexus API: {exc}")
    st.info("Start the FastAPI backend with: uvicorn backend.main:app --reload")
    st.stop()

st.success(f"Connected to FastAPI • {len(events):,} events loaded")

# Session 8 analytics
event_counts = Counter(
    event.get("event_type", "unknown")
    for event in events
)

congestion_events = [
    event
    for event in events
    if event.get("event_type") == "congestion"
]

# Busiest zone: rounded latitude/longitude grouping
zone_counts = Counter()

for event in events:
    try:
        lat = round(float(event["lat"]), 4)
        lon = round(float(event["lon"]), 4)
        zone_counts[(lat, lon)] += 1
    except (KeyError, TypeError, ValueError):
        continue

st.sidebar.header("📊 Analytics")

st.sidebar.metric("Total Events", f"{len(events):,}")

st.sidebar.subheader("Event Breakdown")

if event_counts:
    chart_data = pd.DataFrame(
        {
            "event_type": list(event_counts.keys()),
            "count": list(event_counts.values()),
        }
    ).set_index("event_type")

    st.sidebar.bar_chart(chart_data)

if zone_counts:
    busiest_zone, busiest_count = zone_counts.most_common(1)[0]

    st.sidebar.subheader("📍 Busiest Zone")
    st.sidebar.write(
        f"**{busiest_count:,} events**"
    )
    st.sidebar.caption(
        f"Lat: {busiest_zone[0]:.4f}, "
        f"Lon: {busiest_zone[1]:.4f}"
    )

st.sidebar.subheader("🔥 Congestion")
st.sidebar.metric("Congestion Events", f"{len(congestion_events):,}")

center_lat = sum(lat for lat, _ in ROUTE_POINTS) / len(ROUTE_POINTS)
center_lon = sum(lon for _, lon in ROUTE_POINTS) / len(ROUTE_POINTS)

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=14,
    control_scale=True,
)

folium.PolyLine(
    ROUTE_POINTS,
    tooltip="Kopargaon Bus Stand → Kopargaon Railway Station",
    weight=4,
).add_to(m)

folium.Marker(
    ROUTE_POINTS[0],
    tooltip="Start: Kopargaon MSRTC Bus Stand",
    popup="Route Start",
    icon=folium.Icon(color="green", icon="play"),
).add_to(m)

folium.Marker(
    ROUTE_POINTS[-1],
    tooltip="End: Kopargaon Railway Station",
    popup="Route End",
    icon=folium.Icon(color="red", icon="flag"),
).add_to(m)

# Session 8: congestion heat map weighted by density_score
heatmap_data = []

for event in congestion_events:
    try:
        lat = float(event["lat"])
        lon = float(event["lon"])
        density_score = float(event.get("density_score", 1.0))

        heatmap_data.append([
            lat,
            lon,
            density_score,
        ])
    except (KeyError, TypeError, ValueError):
        continue

if heatmap_data:
    HeatMap(
        heatmap_data,
        name="Congestion Heat Map",
        radius=25,
        blur=18,
        min_opacity=0.4,
    ).add_to(m)

for event in events:
    try:
        lat = float(event["lat"])
        lon = float(event["lon"])
        event_type = event.get("event_type", "unknown")
        confidence = float(event.get("confidence", 0))
        timestamp = event.get("timestamp", "N/A")
        frame_path = event.get("frame_path", "N/A")
        color = EVENT_COLORS.get(event_type, "gray")

        popup_html = f"""
        <b>Event:</b> {event_type}<br>
        <b>Confidence:</b> {confidence:.3f}<br>
        <b>Latitude:</b> {lat:.6f}<br>
        <b>Longitude:</b> {lon:.6f}<br>
        <b>Timestamp:</b> {timestamp}<br>
        <b>Frame:</b> {frame_path}
        """

        folium.CircleMarker(
            location=[lat, lon],
            radius=5,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.75,
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=event_type,
        ).add_to(m)

    except (KeyError, TypeError, ValueError):
        continue

st.subheader("Live Event Map")

if heatmap_data:
    st.caption(
        f"🔥 Congestion heat map active • "
        f"{len(heatmap_data):,} weighted congestion location(s)"
    )
else:
    st.warning("No congestion events available for the heat map.")

st_folium(m, width=None, height=650)
