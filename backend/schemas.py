import base64
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_EVIDENCE_B64_LENGTH = 140_000


class EventType(str, Enum):
    POTHOLE = "pothole"
    PEDESTRIAN_RISK = "pedestrian_risk"
    TRAFFIC_DENSITY = "traffic_density"


class EventSource(str, Enum):
    LIVE = "live"
    REPLAY = "replay"
    SIMULATED = "simulated"


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    bus_id: str
    camera_id: str
    route_id: str
    type: EventType
    confidence: float = Field(ge=0.0, le=1.0)
    severity: str
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    accuracy_m: float = Field(ge=0.0)
    speed_kmh: float
    heading: float
    ts: datetime
    source: EventSource
    evidence_b64: Optional[str] = None

    @field_validator("ts")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include timezone information")

        value_utc = value.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)

        if value_utc > now_utc + timedelta(minutes=5):
            raise ValueError("timestamp cannot be more than 5 minutes in the future")

        return value_utc

    @field_validator("evidence_b64")
    @classmethod
    def validate_evidence(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        if len(value) > MAX_EVIDENCE_B64_LENGTH:
            raise ValueError("evidence_b64 exceeds the 140 KB base64 limit")

        try:
            base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError("evidence_b64 must contain valid Base64 data") from exc

        return value


class HeartbeatStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    camera: bool
    gps: bool
    ai_fps: float
    queue_depth: int


class HeartbeatIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bus_id: str
    lat: float = Field(ge=-90.0, le=90.0)
    lon: float = Field(ge=-180.0, le=180.0)
    accuracy_m: float = Field(ge=0.0)
    speed_kmh: float
    heading: float
    ts: datetime
    status: HeartbeatStatus

    @field_validator("ts")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include timezone information")

        value_utc = value.astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)

        if value_utc > now_utc + timedelta(minutes=5):
            raise ValueError("timestamp cannot be more than 5 minutes in the future")

        return value_utc
