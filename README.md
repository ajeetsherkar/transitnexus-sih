# TransitNexus

AI-powered mobile urban intelligence platform using public transport fleet data.

## Prototype Capabilities

- Vehicle and pedestrian detection using YOLOv8.
- Structured urban event generation with confidence, GPS coordinates, timestamps, and evidence frames.
- Simulated GPS tracking along the Kopargaon Bus Stand → Kopargaon Railway Station route.
- Vehicle detection-density scoring for congestion analysis.
- Predefined pedestrian-risk zone detection.
- FastAPI backend for event and congestion data.
- Streamlit GIS dashboard with live event markers, congestion heat map, analytics, and live incident alerts.
- Prototype incident detection with vehicle evidence frames and plate extraction workflow.

## Incident Plate Extraction

The prototype attempts OCR-based plate extraction using EasyOCR on selected vehicle frames.

For the current demonstration, OCR output was too noisy to reliably identify a real license plate. Therefore, the incident event uses a mock plate value (MH15-TRN-01) with plate_source=mock_ocr and a documented prototype confidence value.

**OCR accuracy to be improved in Phase 2** using better plate-region localization, image preprocessing, multi-frame aggregation, and production-grade license-plate recognition.

## Running the Prototype

Start the FastAPI backend:

    uvicorn backend.main:app --reload

Start the Streamlit dashboard in another terminal:

    streamlit run frontend/app.py

Dashboard: http://localhost:8501

API documentation: http://127.0.0.1:8000/docs

## Architecture

```text
Public Transport Fleet Video
            |
            v
       YOLOv8 Detection
            |
            v
    Structured Event Layer
       /           \
      v             v
 GPS Simulation   Analytics
      |             |
      +------v------+
             |
         FastAPI API
             |
             v
    Streamlit GIS Dashboard
       /       |        \
      v        v         v
   Events   Heat Map   Live Alerts
```

## Prototype Status

This is a demo-grade SIH prototype built using pretrained models. Production deployment would require improved OCR/ALPR, real-time fleet GPS integration, stronger event validation, scalable processing, and deployment infrastructure.
