from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


DEFAULT_DB_PATH = Path(__file__).resolve().parent / "outbox.db"


@dataclass(frozen=True)
class OutboxRow:
    event_id: str
    payload: dict


class Outbox:
    """Small durable SQLite queue for events waiting for uplink."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.db_path,
            timeout=10,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock:
            with self._connect() as db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS outbox (
                        event_id TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                db.commit()

    def enqueue(self, event_id: str, payload: dict) -> bool:
        """Persist an event before attempting network delivery.

        Returns True when inserted, False when the event already exists.
        """
        if not event_id:
            raise ValueError("event_id must not be empty")

        serialized = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        with self._lock:
            with self._connect() as db:
                cursor = db.execute(
                    """
                    INSERT OR IGNORE INTO outbox (
                        event_id,
                        payload,
                        created_at
                    )
                    VALUES (?, ?, datetime('now'))
                    """,
                    (event_id, serialized),
                )
                db.commit()
                return cursor.rowcount == 1

    def oldest(self) -> Optional[OutboxRow]:
        """Return the oldest unsent event, or None."""
        with self._lock:
            with self._connect() as db:
                row = db.execute(
                    """
                    SELECT event_id, payload
                    FROM outbox
                    ORDER BY created_at ASC, rowid ASC
                    LIMIT 1
                    """
                ).fetchone()

        if row is None:
            return None

        return OutboxRow(
            event_id=str(row["event_id"]),
            payload=json.loads(row["payload"]),
        )

    def delete(self, event_id: str) -> None:
        """Delete an event after successful delivery or permanent 4xx rejection."""
        with self._lock:
            with self._connect() as db:
                db.execute(
                    "DELETE FROM outbox WHERE event_id = ?",
                    (event_id,),
                )
                db.commit()

    def count(self) -> int:
        """Return the number of events currently waiting."""
        with self._lock:
            with self._connect() as db:
                row = db.execute(
                    "SELECT COUNT(*) AS count FROM outbox"
                ).fetchone()

        return int(row["count"])

    def clear(self) -> None:
        """Test/helper method to empty the local queue."""
        with self._lock:
            with self._connect() as db:
                db.execute("DELETE FROM outbox")
                db.commit()
