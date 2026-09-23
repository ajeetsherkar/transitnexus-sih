# TransitNexus

**AI-Powered Mobile Urban Intelligence Platform Using Public Transport Fleet**

TransitNexus turns public-transport buses into mobile sensing units. A camera and GPS on each bus generate structured, location-aware mobility events in real time — road hazards, pedestrian risk, and traffic conditions — which are deduplicated across the fleet, verified, and shown live on a GIS control-center dashboard.

> **Smart India Hackathon 2026 — Round 3 Submission**
> Problem Statement: **SIH26124** · Theme: **Smart Automation** · Category: **Software**
> Sponsor: **Bharat Electronics Limited (BEL)** · Team: **TransitNexus** (Team ID 165934)

[![CI](https://github.com/ajeetsherkar/transitnexus-sih/actions/workflows/ci.yml/badge.svg)](https://github.com/ajeetsherkar/transitnexus-sih/actions)

**Live Control Center:** https://transitnexus-v3.onrender.com/dashboard/
**Backend API docs:** https://transitnexus-v3.onrender.com/docs
**Demo video:** _[add link]_

---

## The Problem

1. Urban authorities cannot continuously monitor road conditions across large, complex road networks in real time.
2. Public-transport buses already carry cameras and travel extensively across a city every day, but this video is largely unused for real-time road and incident monitoring.
3. Delayed identification of exact hazard locations slows maintenance, emergency response, and road-safety action.

## Our Solution

TransitNexus converts existing public-transport buses into mobile sensing units, turning camera video into structured, location-aware mobility events in real time.

```text
Video → AI Detection → Structured Events → GIS + ML Intelligence → Actionable Dashboard
```

| | Prototype (what is built and running) | Production target |
|---|---|---|
| Sensing | Live smartphone camera + real-time GPS acting as the bus device | Live bus-mounted camera + vehicle GPS unit |
| Compute | Edge AI on a laptop edge node | On-bus edge computer (Jetson-class / rugged) |
| Backend | Deployed FastAPI + Postgres cloud backend | Same backend, scaled fleet |
| Dashboard | Live GIS control center | Same, with authority-facing workflows |

**Why TransitNexus:**
- Reuses the existing bus fleet — no new fixed sensing network to install
- Converts raw detections into structured, verified, actionable events — not just video
- Deduplicates the same incident reported by multiple buses into a single confirmed record
- Scales from one phone to a full fleet without redesigning the pipeline

---

## Live Architecture

```text
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Phone 1    │  │  Phone 2    │  │  Phone 3    │
│ TN-BUS-001  │  │ TN-BUS-002  │  │ TN-BUS-003  │
│ Camera+GPS  │  │ Camera+GPS  │  │ Camera+GPS  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                         │  HTTPS / WebSocket
                         ▼
              ┌───────────────────────┐
              │  Cloudflare Tunnel    │   exposes the local
              │  (*.trycloudflare.com)│   edge server to phones
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Local Edge Server   │   runs on a laptop today;
              │                       │   Jetson-class device in
              │  YOLOv8 detection     │   production
              │  ByteTrack tracking   │
              │  Event engine         │
              │  Evidence generation  │
              │  SQLite offline outbox│
              └───────────┬───────────┘
                          │  HTTPS REST (events, heartbeat)
                          ▼
              ┌───────────────────────┐
              │  TransitNexus Backend │   deployed on Render
              │  (FastAPI)            │
              │  Per-bus API-key auth │
              │  Dedup engine         │
              │  Incident lifecycle   │
              └───────────┬───────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │   PostgreSQL  │
                  └───────┬───────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Control Center      │   Leaflet dashboard,
              │   (/dashboard/)       │   served by the backend
              │  Fleet + trails       │
              │  Incidents + evidence │
              │  Filters + zones      │
              └───────────────────────┘
```

**Where each piece runs:**

| Component | Location | Purpose |
|---|---|---|
| Mobile client | Phone (browser) | Camera + GPS sensing, no app install needed |
| Cloudflare Tunnel | Internet | Exposes the local edge server to phones over HTTPS (required for camera/GPS permissions) |
| Edge server | Local laptop today | ML inference, tracking, event generation, offline outbox |
| FastAPI backend | Render (cloud) | Authentication, ingestion, deduplication, incident lifecycle, API |
| Database | Render-hosted Postgres | Persistent buses, positions, reports, incidents |
| Control Center | Render, served at `/dashboard/` | Fleet map, live alerts, filters, incident detail, evidence |

Only structured events, heartbeats, and a small evidence image leave the edge node — raw video is never uploaded. This keeps the design practical as the fleet grows.

---

## Technical Approach

| Layer | What it does | Technologies |
|---|---|---|
| 1. Mobile Sensing | Phone camera + GPS act as the bus device | Camera, GPS, Bus ID, WebSocket |
| 2. Edge AI | Detects and tracks road hazards, vehicles, and pedestrians | YOLOv8, OpenCV, ByteTrack, Event Engine |
| 3. Connectivity | Gets phone data to the edge node and events to the cloud reliably | Cloudflare Tunnel, SQLite Outbox, Retry/Backoff |
| 4. Cloud Intelligence | Authenticates, validates, and deduplicates incoming reports | FastAPI, Ingestion API, Dedup Engine, Incident Verification |
| 5. GIS Control Center | Presents fleet and incidents to an operator | Leaflet, Fleet Monitoring, Incident Detail, Evidence |

**Core technologies:** Python · Ultralytics (YOLOv8) · FastAPI · WebSocket · SQLite · PostgreSQL · Leaflet

Each layer runs independently — a single bus camera can generate structured events today, while the same pipeline scales to a full fleet without redesign.

---

## Key Features

### 1. Live Phone-Based Sensing
A phone's rear camera and GPS act as a bus's camera and GPS unit — no dedicated hardware needed to validate the pipeline. Frames stream to the edge server over a secure WebSocket; GPS updates (lat, lon, accuracy, speed, heading) stream alongside them.

### 2. Edge Detection and Tracking
YOLOv8 detects road hazards, vehicles, and pedestrians on each frame. ByteTrack assigns a stable track ID to each object across frames, so one pothole or one pedestrian is counted once, not once per frame.

### 3. Structured Event Generation
Confirmed detections (not raw per-frame boxes) become events, each with an event type, confidence, GPS location, timestamp, bus/camera ID, and a small evidence image.

### 4. Multi-Bus Deduplication
The core Round-3 capability: when multiple buses report the same real-world incident, TransitNexus merges them into a single incident record instead of creating duplicate alerts.

- **Type-aware matching** — different rules for a static hazard (pothole) vs. a transient one (pedestrian risk)
- **Spatial matching** — a distance radius that widens with the reporting phone's GPS accuracy, since phone GPS is typically off by 5–20 m
- **Temporal matching** — reports must fall within a type-specific time window
- **Same-bus guard** — a bus re-reporting the same spot doesn't inflate the confirming-bus count
- **Confidence fusion** — merged confidence is computed across all contributing buses' best detections

**Validated results:**

| Test | Reports submitted | Result |
|---|---|---|
| Simulated fleet, single pothole | 14 reports from 10 simulated buses | Collapsed to **1 incident**, `bus_count: 10`, status `VERIFIED` |
| Real-device field test, single pothole | 44 reports from 3 physical phones | Collapsed to **1 incident**, `bus_count: 3`, status `VERIFIED` |

### 5. Incident Lifecycle
Incidents move through `DETECTED` (1 bus) → `VERIFIED` (2+ distinct buses) → `RESOLVED` (operator action). A new detection at a resolved location opens a new incident linked as a **recurrence** — useful for flagging a repair that didn't hold.

### 6. Reliable Uplink (Offline Queue)
Events are written to a local SQLite outbox before being sent. If the network drops, the uplink thread retries with exponential backoff; events are idempotent on `event_id`, so retries never create duplicates. A dead-letter table catches requests that can never succeed (e.g. bad auth) so they don't block the queue.

### 7. Per-Bus Authentication
Every bus/phone authenticates with its own API key (stored server-side only as a hash). A key that doesn't match its claimed `bus_id` is rejected. Read endpoints require a separate read token so the live data isn't publicly scrapeable.

### 8. GIS Control Center Dashboard
- Live fleet map: bus markers (online/offline), bus trails, follow-bus mode
- Live incident markers, colour-coded by status, with type icons
- KPI strip: buses online/offline, open incidents, reports today
- Filters by bus, route, event type, severity, status, time window
- Incident detail panel: status timeline, contributing buses, fused confidence, evidence image
- Access-code overlay so the live dashboard isn't open to anyone with the link

### 9. Multi-Bus Fleet Simulator
`tools/simulate_fleet.py` drives simulated buses along real drawn routes with realistic GPS noise, for testing and demoing fleet-scale behaviour (including the same-pothole dedup scenario) without needing physical devices every time.

---

## Honest Performance Numbers

Measured during outdoor field testing with physical phones over a live Cloudflare tunnel, not a lab benchmark:

| Metric | Result |
|---|---|
| Edge inference latency | ~67–76 ms per frame |
| Achieved field frame rate | ~0.2–0.9 fps per phone |
| Pothole model precision | 78.2% |
| Pothole model mAP@50 | 74.3% |
| Dedup validation (simulated) | 10 buses → 1 incident |
| Dedup validation (real devices) | 3 phones, 44 reports → 1 incident |

**We report this frame rate honestly rather than calling it real-time.** At ~0.2–0.9 fps, the system is near-real-time on current hardware (a laptop edge node over a phone's mobile connection), not continuous high-frame-rate video analytics. The architecture is designed for this to improve significantly on dedicated edge hardware (Jetson-class) rather than a laptop, which is the direct production path — the API, dedup engine, and dashboard do not change when the edge node changes.

---

## Real vs Simulated vs Production

| Component | Current state | Evidence | Production plan |
|---|---|---|---|
| Phone camera stream + edge processing | **Real, live** | Field-test recordings, live dashboard | Same pipeline, bus-mounted camera |
| Pothole detection | **Real**, limited accuracy | Model card: 78.2% precision, 74.3% mAP@50 | Retrain on larger, road-specific dataset |
| Person / vehicle detection | **Real** (pretrained YOLOv8 COCO classes) | Annotated detection video | Same |
| Object tracking (ByteTrack) | **Real** | Stable track IDs in annotated video | Same |
| Live GPS | **Real** (phone GPS, ~5–20 m accuracy) | Live bus trails on dashboard | Vehicle-grade GPS unit |
| Multi-bus fleet | **Real** (2–3 physical phones) + simulated buses for scale testing | Dashboard fleet badges | Full physical fleet |
| Deduplication | **Real algorithm**, tested with simulated and real devices | Validation table above | Same algorithm at fleet scale |
| Offline queue | **Real**, tested with a live network cut | Field-test log | Same |
| Backend + database | **Real**, deployed (Render + Postgres) | Live API at `/docs` | Same, scaled infrastructure |
| Congestion / route-delay ML (Round 2 legacy) | Prototype models trained on engineered/simulated features | `models/` in repo | Retrain on real fleet + traffic ground truth, or drop |
| Plate OCR / hit-and-run | **Simulated** (Round 2 prototype only) | Labelled `mock_ocr` in event data | Production-grade ALPR |
| ONNX export | **Real**, benchmarked on a laptop CPU | Benchmark table in `docs/` | Evaluate on target edge hardware |
| Jetson / rugged edge hardware | **Roadmap** — not tested | — | Primary production hardware target |
| PostGIS, Kafka/Redis, RBAC | **Roadmap** | — | Needed at full fleet scale |

> **Judge-ready answer:** *"We validated the full event-to-intelligence pipeline live, using a phone's camera and GPS as the bus device, with real edge inference, real deduplication across real devices, and a deployed cloud backend. Production replaces the phone with a bus-mounted camera and GPS unit on the same architecture — the API, dedup engine, and dashboard do not change."*

---

## Feasibility Snapshot

- **2,606** events processed across prototype validation (Round 2 baseline) plus live Round 3 field testing
- **5** core technologies proven end-to-end in a deployed system
- End-to-end pipeline validated: video → detection → event → dedup → dashboard

| Challenge | Mitigation |
|---|---|
| Video quality, lighting, and motion variation | Confidence thresholds + temporal/spatial deduplication |
| Duplicate events across frames and across buses | ByteTrack (within-camera) + spatio-temporal dedup engine (cross-bus) |
| Real-world data and ground-truth requirements | Field-test data collection; retraining path documented |
| Edge compute, connectivity, security, storage | Edge inference, offline outbox, per-bus API keys, event-first (not video) transmission |

---

## Impact

**Authorities** — real-time, location-linked road intelligence and faster incident response, without new fixed sensing infrastructure.

**Commuters** — safer roads through faster hazard detection and repair prioritization.

**Law enforcement** — location-linked, timestamped incident evidence to support investigation.

**Economic** — reuses the existing bus fleet instead of funding a new city-wide sensor network.

---

## API Endpoints

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/v1/events` | bus key | Ingest one event; idempotent on `event_id`; runs the dedup engine |
| POST | `/v1/heartbeat` | bus key | Latest position and device status (camera, GPS, fps, queue depth) |
| GET | `/v1/buses` | read token | Fleet list with online/offline status and last-seen age |
| GET | `/v1/buses/{id}/trail` | read token | Recent GPS positions for a bus's live trail |
| GET | `/v1/incidents` | read token | Incidents, filterable by type, status, bus, zone, time |
| GET | `/v1/incidents/{id}` | read token | Incident detail: contributing buses, evidence, status timeline |
| POST | `/v1/incidents/{id}/resolve` | admin token | Mark an incident resolved (a later detection opens a recurrence) |
| GET | `/v1/evidence/{event_id}.jpg` | read token | Evidence image for an event |
| GET | `/v1/zones` | read token | Per-zone aggregates |
| GET | `/v1/stats` | read token | Counters and latency (median / p95) |
| GET | `/health` | none | Liveness check |

Full interactive documentation: https://transitnexus-v3.onrender.com/docs

---

## Running the Live System

### 1. Backend and dashboard (already deployed — no setup needed to view)

- Control Center: https://transitnexus-v3.onrender.com/dashboard/
- API docs: https://transitnexus-v3.onrender.com/docs

### 2. Running the edge server locally (to stream from a phone)

```bash
PYTHONPATH=. TRANSITNEXUS_BACKEND_URL=https://transitnexus-v3.onrender.com \
  python edge/server.py --host 0.0.0.0 --port 8000
```

### 3. Expose it to a phone over HTTPS (required for camera/GPS permissions)

```bash
cloudflared tunnel --protocol http2 --url http://localhost:8000
```

This prints a temporary URL like `https://<random-name>.trycloudflare.com` — a fresh one is generated every time the tunnel starts.

### 4. Open the mobile client on a phone

```text
https://<cloudflare-url>.trycloudflare.com/client
```

Enter the bus ID (e.g. `TN-BUS-001`) and its API key, grant camera and location permissions, and start sensing. Detection boxes render live on the phone; events appear on the Control Center within seconds.

### 5. Multi-device field test

| Device | Bus ID |
|---|---|
| Phone 1 | `TN-BUS-001` |
| Phone 2 | `TN-BUS-002` |
| Phone 3 | `TN-BUS-003` |

All phones use the same tunnel `/client` URL with different bus IDs and credentials.

> API keys and Cloudflare tunnel URLs are per-session secrets and are intentionally not published in this README.

### 6. Simulating a fleet without physical devices

```bash
python tools/simulate_fleet.py --buses 10 --scenario same-pothole --url https://transitnexus-v3.onrender.com --keys keys.json
python tools/check_dedup.py
```

---

## Project Structure

```text
transitnexus-sih/
│
├── backend/                 # FastAPI cloud backend (deployed on Render)
│   ├── models.py            # SQLAlchemy models: Bus, Position, Report, Incident
│   ├── db.py
│   ├── routes.py            # /v1/events, /v1/heartbeat, /v1/incidents, ...
│   ├── dedup.py             # spatio-temporal deduplication engine
│   ├── geo.py
│   ├── auth.py
│   ├── schemas.py
│   └── tests/
│
├── edge/                    # Local edge node (runs on a laptop today)
│   ├── server.py            # WebSocket streaming server
│   ├── detector.py          # YOLOv8 + ByteTrack
│   ├── events.py            # detection → structured event logic
│   ├── outbox.py            # offline SQLite queue
│   ├── uplink.py            # retry / backoff uploader
│   ├── static/client.html   # phone-facing mobile sensing client
│   └── weights/              # model weights (not committed to git)
│
├── dashboard/
│   └── control-center/      # Leaflet GIS control center, served at /dashboard/
│
├── ml/                       # Pothole model training and evaluation
│   ├── train_pothole.py
│   └── evaluate_pothole.py
│
├── tools/                    # Fleet simulator, dedup checks, admin scripts
│   ├── simulate_fleet.py
│   ├── check_dedup.py
│   ├── create_bus_key.py
│   └── import_round2_events.py
│
├── docs/
│   ├── API_CONTRACT.md
│   ├── MODEL_CARD.md
│   ├── RESULTS.md
│   ├── field-test-1.md
│   └── field-test-2.md
│
├── .github/workflows/ci.yml
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Round 2 → Round 3: What Changed

| | Round 2 | Round 3 |
|---|---|---|
| Video source | Pre-recorded sample clips | Live phone camera stream |
| GPS | Simulated along a fixed route | Real phone GPS |
| Object tracking | None (per-frame detection only) | ByteTrack, stable IDs |
| Duplicate handling | None | Type-aware spatio-temporal dedup engine, validated with real and simulated buses |
| Storage | `events.json` | PostgreSQL |
| Auth | None (open endpoints) | Per-bus hashed API keys, read/admin tokens |
| Network resilience | None | SQLite offline outbox with retry/backoff |
| Dashboard | Single-bus event map | Multi-bus fleet control center with trails, filters, incident lifecycle |
| Pothole model | Generic pretrained weights | Fine-tuned TransitNexus pothole model (precision 78.2%, mAP@50 74.3%) |

---

## Team

Ajeet Sherkar
Onkar Jha 
Pradnya Mhaske
Gajanan Jorvekar
Sakshi Zinjurde
Yashraj Gade

**TransitNexus — SIH 2026 — SIH26124**
AI-Powered Mobile Urban Intelligence Platform Using Public Transport Fleet · Software Category

## Screenshots

_[Add Control Center screenshots here]_

## Research and References

1. Bharat Electronics Limited (BEL) — SIH26124 Problem Statement Brief, sih.gov.in
2. Ultralytics YOLOv8 — Real-time Object Detection, docs.ultralytics.com
3. RDD2022 — Road Damage Dataset (pothole / road-damage detection)
4. ONNX Runtime — Edge Inference and Deployment, onnxruntime.ai
5. Scikit-learn — Machine Learning and Model Evaluation, scikit-learn.org
6. Live prototype and code: github.com/ajeetsherkar/transitnexus-sih

## License

Developed as a Smart India Hackathon 2026 prototype and demonstration system.