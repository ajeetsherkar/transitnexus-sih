# TransitNexus API Contract v1

## Purpose

This document is the shared contract between the edge client, central backend,
and dashboard.

All timestamps are UTC and use ISO 8601 format.

---

## Event JSON

```json
{
  "event_id": "uuid4",
  "bus_id": "TN-BUS-001",
  "camera_id": "CAM-001",
  "route_id": "R-01",
  "type": "pothole",
  "confidence": 0.87,
  "severity": "high",
  "lat": 19.9021,
  "lon": 74.4944,
  "accuracy_m": 8.0,
  "speed_kmh": 24.5,
  "heading": 87,
  "ts": "2026-09-21T10:01:07Z",
  "source": "live",
  "evidence_b64": "..."
}
```

### Event Fields

| Field | Type | Description |
|---|---|---|
| event_id | UUID | Unique event identifier |
| bus_id | string | Unique bus identifier |
| camera_id | string | Camera identifier |
| route_id | string | Route identifier |
| type | string | `pothole`, `pedestrian_risk`, or `traffic_density` |
| confidence | float | Model confidence from 0 to 1 |
| severity | string | Event severity |
| lat | float | Latitude |
| lon | float | Longitude |
| accuracy_m | float | GPS accuracy in metres |
| speed_kmh | float | Vehicle speed |
| heading | float | Vehicle heading in degrees |
| ts | string | UTC ISO 8601 timestamp |
| source | string | `live`, `replay`, or `simulated` |
| evidence_b64 | string | Optional JPEG evidence encoded as Base64 |

---

## Heartbeat JSON

```json
{
  "bus_id": "TN-BUS-001",
  "lat": 19.9021,
  "lon": 74.4944,
  "accuracy_m": 8.0,
  "speed_kmh": 24.5,
  "heading": 87,
  "ts": "2026-09-21T10:01:07Z",
  "status": {
    "camera": true,
    "gps": true,
    "ai_fps": 2.1,
    "queue_depth": 0
  }
}
```

---

## API Endpoints

| Method | Endpoint | Authentication | Purpose |
|---|---|---|---|
| POST | `/v1/events` | Bus API key | Submit an event |
| POST | `/v1/heartbeat` | Bus API key | Submit bus heartbeat |
| GET | `/v1/buses` | Read token | List active buses |
| GET | `/v1/buses/{id}/trail` | Read token | Get bus location trail |
| GET | `/v1/incidents` | Read token | List incidents |
| GET | `/v1/incidents/{id}` | Read token | Get incident details |
| POST | `/v1/incidents/{id}/resolve` | Admin token | Resolve an incident |
| GET | `/v1/evidence/{event_id}.jpg` | Read token | Retrieve event evidence |
| GET | `/v1/zones` | Read token | Get monitored zones |
| GET | `/v1/stats` | Read token | Get system statistics |
| GET | `/health` | None | Health check |

---

## Incident Filters

`GET /v1/incidents` supports:

- `type`
- `status`
- `bus_id`
- `since`
- `zone`

---

## Bus Trail

`GET /v1/buses/{id}/trail`

The default trail window is the previous 30 minutes.

---

## Authentication

### Bus API Key

Used by edge clients when sending:

- events
- heartbeats

Each bus has its own API key.

### Read Token

Used by dashboard clients to access read-only endpoints.

### Admin Token

Used for administrative actions such as resolving incidents.

---

## Status Codes

| Code | Meaning |
|---|---|
| 200 | Request stored successfully or duplicate event detected |
| 401 | Authentication failed |
| 403 | API key is not valid for the requested bus |
| 422 | Request validation failed |
| 429 | Rate limit exceeded |

Edge clients retry non-2xx responses except:

- 400
- 401
- 403
- 422

---

## Contract Rules

1. `event_id` must be unique and is used for idempotency.
2. Repeated submission of the same `event_id` must not create another event.
3. Latitude must be between -90 and 90.
4. Longitude must be between -180 and 180.
5. Confidence must be between 0 and 1.
6. `accuracy_m` must be greater than or equal to 0.
7. Timestamps must be UTC ISO 8601.
8. Events more than 5 minutes in the future must be rejected.
9. Evidence is optional.
10. Evidence must be JPEG and no larger than 100 KB.
11. Allowed event types are:
    - `pothole`
    - `pedestrian_risk`
    - `traffic_density`
12. Allowed sources are:
    - `live`
    - `replay`
    - `simulated`

---

## Version

**API Contract:** v1  
**Round:** SIH 2026 Round 3  
**Problem Statement:** SIH26124
