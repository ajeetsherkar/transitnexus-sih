# TransitNexus Pipeline

1. Traffic videos are processed with YOLOv8 for vehicle and pedestrian detection.
2. Detected objects are converted into structured urban mobility events with confidence, GPS, timestamp, and frame path.
3. GPS coordinates are simulated along the Kopargaon Bus Stand to Railway Station route for prototype events.
4. Vehicle detection counts are aggregated into 5-second windows to generate congestion events, while a predefined zone is used for pedestrian-risk events.
5. Events and representative event crops are stored in `data/processed/events.json` and `data/processed/events/`.
6. FastAPI serves the processed events through `/events` and congestion heatmap data through `/heatmap-data`.
