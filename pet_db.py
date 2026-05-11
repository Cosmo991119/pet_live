"""
SQLite persistence layer for the pet agent.

This module owns the structured fact store. LLM-generated text should depend on
data stored here, but factual state changes should not depend on the LLM.
"""

from pathlib import Path
from datetime import date, datetime, time, timedelta
import json
import sqlite3
from typing import Any, Optional, Union


DB_PATH = Path("pet_agent.db")
ALLOWED_PET_MODES = {"real", "virtual"}
ALLOWED_SPECIES = {"cat", "dog", "other"}
ALLOWED_PERSONALITIES = {"sweet", "cool", "energetic", "gentle"}
ALLOWED_BEHAVIORS = {"eat", "drink", "poop", "play", "sleep_start", "sleep_end"}
SESSION_BEHAVIORS = {"eat", "drink", "poop", "play"}
CONFIDENCE_NOTIFY_THRESHOLD = 0.7
RAW_EVENT_RETENTION_DAYS = 90
SESSION_WINDOWS_SECONDS = {
    "eat": 10 * 60,
    "drink": 5 * 60,
    "poop": 15 * 60,
    "play": 20 * 60,
}


DbPath = Union[Path, str]


def connect(db_path: DbPath = DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with project defaults enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def _table_sql(conn: sqlite3.Connection, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row["sql"] if row else ""


def _migrate_play_behavior(conn: sqlite3.Connection) -> None:
    """Upgrade older local databases whose CHECK constraints do not allow play."""
    events_sql = _table_sql(conn, "events")
    sessions_sql = _table_sql(conn, "behavior_sessions")
    if "'play'" in events_sql and "'play'" in sessions_sql:
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    if "'play'" not in events_sql:
        conn.executescript(
            """
            ALTER TABLE events RENAME TO events_old;

            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                behavior TEXT NOT NULL CHECK (
                    behavior IN (
                        'eat',
                        'drink',
                        'poop',
                        'play',
                        'sleep_start',
                        'sleep_end'
                    )
                ),
                location_name TEXT,
                occurred_at TEXT NOT NULL,
                confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                status TEXT NOT NULL CHECK (
                    status IN (
                        'confirmed',
                        'low_confidence',
                        'duplicate',
                        'ignored',
                        'corrected'
                    )
                ),
                raw_payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            INSERT INTO events (
                id,
                pet_id,
                behavior,
                location_name,
                occurred_at,
                confidence,
                status,
                raw_payload,
                created_at
            )
            SELECT
                id,
                pet_id,
                behavior,
                location_name,
                occurred_at,
                confidence,
                status,
                raw_payload,
                created_at
            FROM events_old;

            DROP TABLE events_old;
            """
        )

    if "'play'" not in sessions_sql:
        conn.executescript(
            """
            ALTER TABLE behavior_sessions RENAME TO behavior_sessions_old;

            CREATE TABLE behavior_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                behavior TEXT NOT NULL CHECK (
                    behavior IN ('eat', 'drink', 'poop', 'play')
                ),
                location_name TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                raw_event_count INTEGER NOT NULL DEFAULT 1 CHECK (raw_event_count >= 1),
                status TEXT NOT NULL DEFAULT 'active' CHECK (
                    status IN ('active', 'closed', 'ignored', 'corrected')
                ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            INSERT INTO behavior_sessions (
                id,
                pet_id,
                behavior,
                location_name,
                start_time,
                end_time,
                raw_event_count,
                status,
                created_at,
                updated_at
            )
            SELECT
                id,
                pet_id,
                behavior,
                location_name,
                start_time,
                end_time,
                raw_event_count,
                status,
                created_at,
                updated_at
            FROM behavior_sessions_old;

            DROP TABLE behavior_sessions_old;
            """
        )

    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_events_pet_behavior_time
        ON events (pet_id, behavior, occurred_at);

        CREATE INDEX IF NOT EXISTS idx_behavior_sessions_pet_behavior_time
        ON behavior_sessions (pet_id, behavior, start_time, end_time);
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def init_db(db_path: DbPath = DB_PATH) -> Path:
    """Create all pet agent tables if they do not already exist."""
    db_path = Path(db_path)
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                pet_mode TEXT NOT NULL DEFAULT 'real' CHECK (
                    pet_mode IN ('real', 'virtual')
                ),
                species TEXT NOT NULL CHECK (species IN ('cat', 'dog', 'other')),
                personality TEXT NOT NULL CHECK (
                    personality IN ('sweet', 'cool', 'energetic', 'gentle')
                ),
                owner_call_name TEXT NOT NULL,
                profile_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                behavior TEXT NOT NULL CHECK (
                    behavior IN (
                        'eat',
                        'drink',
                        'poop',
                        'play',
                        'sleep_start',
                        'sleep_end'
                    )
                ),
                location_name TEXT,
                occurred_at TEXT NOT NULL,
                confidence REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
                status TEXT NOT NULL CHECK (
                    status IN (
                        'confirmed',
                        'low_confidence',
                        'duplicate',
                        'ignored',
                        'corrected'
                    )
                ),
                raw_payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_events_pet_behavior_time
            ON events (pet_id, behavior, occurred_at);

            CREATE TABLE IF NOT EXISTS archived_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_event_id INTEGER NOT NULL UNIQUE,
                pet_id INTEGER NOT NULL,
                behavior TEXT NOT NULL,
                location_name TEXT,
                occurred_at TEXT NOT NULL,
                confidence REAL NOT NULL,
                status TEXT NOT NULL,
                raw_payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                archive_reason TEXT NOT NULL,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_archived_events_pet_behavior_time
            ON archived_events (pet_id, behavior, occurred_at);

            CREATE TABLE IF NOT EXISTS behavior_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                behavior TEXT NOT NULL CHECK (
                    behavior IN ('eat', 'drink', 'poop', 'play')
                ),
                location_name TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                raw_event_count INTEGER NOT NULL DEFAULT 1 CHECK (raw_event_count >= 1),
                status TEXT NOT NULL DEFAULT 'active' CHECK (
                    status IN ('active', 'closed', 'ignored', 'corrected')
                ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_behavior_sessions_pet_behavior_time
            ON behavior_sessions (pet_id, behavior, start_time, end_time);

            CREATE TABLE IF NOT EXISTS sleep_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                start_event_id INTEGER NOT NULL,
                end_event_id INTEGER,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_minutes INTEGER,
                status TEXT NOT NULL CHECK (
                    status IN ('active', 'completed', 'ignored', 'corrected')
                ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id),
                FOREIGN KEY (start_event_id) REFERENCES events(id),
                FOREIGN KEY (end_event_id) REFERENCES events(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sleep_sessions_pet_status
            ON sleep_sessions (pet_id, status);

            CREATE TABLE IF NOT EXISTS anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                event_id INTEGER,
                anomaly_type TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id),
                FOREIGN KEY (event_id) REFERENCES events(id)
            );

            CREATE TABLE IF NOT EXISTS event_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                session_id INTEGER,
                pet_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL CHECK (severity IN ('normal', 'info', 'warning')),
                facts_used_json TEXT NOT NULL,
                internal_signal TEXT,
                model_name TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id) REFERENCES events(id),
                FOREIGN KEY (session_id) REFERENCES behavior_sessions(id),
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_event_messages_pet_created
            ON event_messages (pet_id, created_at);

            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                range_type TEXT NOT NULL CHECK (range_type IN ('day', 'week', 'month')),
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                stats_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                model_name TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_summaries_pet_range
            ON summaries (pet_id, range_type, start_date, end_date);

            CREATE TABLE IF NOT EXISTS virtual_pet_states (
                pet_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                current_time TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );
            """
        )
        if not _column_exists(conn, "pets", "pet_mode"):
            conn.execute(
                "ALTER TABLE pets ADD COLUMN pet_mode TEXT NOT NULL DEFAULT 'real'"
            )
        _migrate_play_behavior(conn)
    return db_path


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def create_pet(
    name: str,
    species: str,
    personality: str,
    owner_call_name: str,
    pet_mode: str = "real",
    profile: Optional[dict[str, Any]] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Create a pet record and return it as a dictionary."""
    if pet_mode not in ALLOWED_PET_MODES:
        raise ValueError(f"pet_mode must be one of {sorted(ALLOWED_PET_MODES)}")
    if species not in ALLOWED_SPECIES:
        raise ValueError(f"species must be one of {sorted(ALLOWED_SPECIES)}")
    if personality not in ALLOWED_PERSONALITIES:
        raise ValueError(
            f"personality must be one of {sorted(ALLOWED_PERSONALITIES)}"
        )
    if not name.strip():
        raise ValueError("name is required")
    if not owner_call_name.strip():
        raise ValueError("owner_call_name is required")

    profile_json = json.dumps(profile or {}, ensure_ascii=False)

    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO pets (
                name,
                pet_mode,
                species,
                personality,
                owner_call_name,
                profile_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, pet_mode, species, personality, owner_call_name, profile_json),
        )
        pet_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()

    return _row_to_dict(row)


def update_pet(
    pet_id: int,
    name: Optional[str] = None,
    species: Optional[str] = None,
    personality: Optional[str] = None,
    owner_call_name: Optional[str] = None,
    pet_mode: Optional[str] = None,
    profile: Optional[dict[str, Any]] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Partially update a pet profile and return the updated row."""
    updates: list[str] = []
    params: list[Any] = []

    if name is not None:
        if not name.strip():
            raise ValueError("name cannot be empty")
        updates.append("name = ?")
        params.append(name)
    if species is not None:
        if species not in ALLOWED_SPECIES:
            raise ValueError(f"species must be one of {sorted(ALLOWED_SPECIES)}")
        updates.append("species = ?")
        params.append(species)
    if personality is not None:
        if personality not in ALLOWED_PERSONALITIES:
            raise ValueError(
                f"personality must be one of {sorted(ALLOWED_PERSONALITIES)}"
            )
        updates.append("personality = ?")
        params.append(personality)
    if owner_call_name is not None:
        if not owner_call_name.strip():
            raise ValueError("owner_call_name cannot be empty")
        updates.append("owner_call_name = ?")
        params.append(owner_call_name)
    if pet_mode is not None:
        if pet_mode not in ALLOWED_PET_MODES:
            raise ValueError(f"pet_mode must be one of {sorted(ALLOWED_PET_MODES)}")
        updates.append("pet_mode = ?")
        params.append(pet_mode)
    if profile is not None:
        updates.append("profile_json = ?")
        params.append(json.dumps(profile, ensure_ascii=False))

    with connect(db_path) as conn:
        pet = conn.execute("SELECT id FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if pet is None:
            raise ValueError(f"pet_id {pet_id} does not exist")

        if updates:
            params.append(pet_id)
            conn.execute(
                f"UPDATE pets SET {', '.join(updates)} WHERE id = ?",
                params,
            )

        row = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()

    return _row_to_dict(row)


def save_virtual_pet_state(
    pet_id: int,
    state: dict[str, Any],
    current_time: str,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Insert or update the persisted virtual pet state."""
    state_json = json.dumps(state, ensure_ascii=False)
    with connect(db_path) as conn:
        pet = conn.execute("SELECT id FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if pet is None:
            raise ValueError(f"pet_id {pet_id} does not exist")

        conn.execute(
            """
            INSERT INTO virtual_pet_states (
                pet_id,
                state_json,
                current_time,
                updated_at
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(pet_id) DO UPDATE SET
                state_json = excluded.state_json,
                current_time = excluded.current_time,
                updated_at = CURRENT_TIMESTAMP
            """,
            (pet_id, state_json, current_time),
        )
        row = conn.execute(
            "SELECT * FROM virtual_pet_states WHERE pet_id = ?", (pet_id,)
        ).fetchone()
    return _row_to_dict(row)


def get_virtual_pet_state(
    pet_id: int,
    db_path: DbPath = DB_PATH,
) -> Optional[dict[str, Any]]:
    """Return the persisted virtual pet state row, or None if missing."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM virtual_pet_states WHERE pet_id = ?", (pet_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def get_pet(pet_id: int, db_path: DbPath = DB_PATH) -> Optional[dict[str, Any]]:
    """Return one pet by id, or None if it does not exist."""
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM pets WHERE id = ?", (pet_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_pets(db_path: DbPath = DB_PATH) -> list[dict[str, Any]]:
    """Return all pets ordered by creation time."""
    with connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM pets ORDER BY created_at ASC, id ASC"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def record_event(
    pet_id: int,
    behavior: str,
    location_name: Optional[str],
    occurred_at: str,
    confidence: float,
    raw_payload: Optional[dict[str, Any]] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Validate and store one raw behavior event."""
    if behavior not in ALLOWED_BEHAVIORS:
        raise ValueError(f"behavior must be one of {sorted(ALLOWED_BEHAVIORS)}")
    if confidence < 0 or confidence > 1:
        raise ValueError("confidence must be between 0 and 1")
    if not occurred_at.strip():
        raise ValueError("occurred_at is required")

    payload = raw_payload or {
        "pet_id": pet_id,
        "behavior": behavior,
        "location_name": location_name,
        "occurred_at": occurred_at,
        "confidence": confidence,
    }
    payload_json = json.dumps(payload, ensure_ascii=False)
    status = (
        "confirmed"
        if confidence >= CONFIDENCE_NOTIFY_THRESHOLD
        else "low_confidence"
    )

    with connect(db_path) as conn:
        pet = conn.execute("SELECT id FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if pet is None:
            raise ValueError(f"pet_id {pet_id} does not exist")

        cursor = conn.execute(
            """
            INSERT INTO events (
                pet_id,
                behavior,
                location_name,
                occurred_at,
                confidence,
                status,
                raw_payload
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pet_id,
                behavior,
                location_name,
                occurred_at,
                confidence,
                status,
                payload_json,
            ),
        )
        event_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()

    return _row_to_dict(row)


def archive_raw_events_before(
    cutoff: str,
    reason: str = "retention_policy",
    dry_run: bool = False,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """
    Archive and delete old raw events that are safe to remove.

    Events referenced by generated messages, sleep sessions, or anomalies are
    kept in place so existing foreign-key relationships remain valid.
    """
    if not cutoff.strip():
        raise ValueError("cutoff is required")
    if not reason.strip():
        raise ValueError("reason is required")
    _parse_iso_datetime(cutoff)

    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT e.*
            FROM events e
            WHERE e.occurred_at < ?
              AND NOT EXISTS (
                  SELECT 1 FROM event_messages m WHERE m.event_id = e.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM sleep_sessions s
                  WHERE s.start_event_id = e.id OR s.end_event_id = e.id
              )
              AND NOT EXISTS (
                  SELECT 1 FROM anomalies a WHERE a.event_id = e.id
              )
            ORDER BY e.occurred_at ASC, e.id ASC
            """,
            (cutoff,),
        ).fetchall()

        event_ids = [row["id"] for row in rows]
        if dry_run or not event_ids:
            return {
                "cutoff": cutoff,
                "reason": reason,
                "dry_run": dry_run,
                "eligible_count": len(event_ids),
                "archived_count": 0,
                "deleted_count": 0,
            }

        conn.executemany(
            """
            INSERT OR IGNORE INTO archived_events (
                original_event_id,
                pet_id,
                behavior,
                location_name,
                occurred_at,
                confidence,
                status,
                raw_payload,
                created_at,
                archive_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["id"],
                    row["pet_id"],
                    row["behavior"],
                    row["location_name"],
                    row["occurred_at"],
                    row["confidence"],
                    row["status"],
                    row["raw_payload"],
                    row["created_at"],
                    reason,
                )
                for row in rows
            ],
        )
        archived_count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM archived_events
            WHERE original_event_id IN ({})
            """.format(",".join("?" for _ in event_ids)),
            event_ids,
        ).fetchone()["count"]

        conn.executemany(
            "DELETE FROM events WHERE id = ?",
            [(event_id,) for event_id in event_ids],
        )

    return {
        "cutoff": cutoff,
        "reason": reason,
        "dry_run": False,
        "eligible_count": len(event_ids),
        "archived_count": archived_count,
        "deleted_count": len(event_ids),
    }


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _session_window_start(occurred_at: str, behavior: str) -> str:
    occurred = _parse_iso_datetime(occurred_at)
    window = timedelta(seconds=SESSION_WINDOWS_SECONDS[behavior])
    return (occurred - window).isoformat()


def upsert_behavior_session(
    event: dict[str, Any],
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """
    Create or update a behavior session for eat/drink/poop/play events.

    Returns:
        {
            "session": {...},
            "is_new_session": bool
        }
    """
    behavior = event["behavior"]
    if behavior not in SESSION_BEHAVIORS:
        raise ValueError(f"behavior sessions only support {sorted(SESSION_BEHAVIORS)}")
    if event["status"] != "confirmed":
        return {"session": None, "is_new_session": False}

    pet_id = event["pet_id"]
    location_name = event["location_name"]
    occurred_at = event["occurred_at"]
    window_start = _session_window_start(occurred_at, behavior)

    with connect(db_path) as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM behavior_sessions
            WHERE pet_id = ?
              AND behavior = ?
              AND COALESCE(location_name, '') = COALESCE(?, '')
              AND status = 'active'
              AND end_time >= ?
              AND end_time <= ?
            ORDER BY end_time DESC, id DESC
            LIMIT 1
            """,
            (pet_id, behavior, location_name, window_start, occurred_at),
        ).fetchone()

        if existing:
            conn.execute(
                """
                UPDATE behavior_sessions
                SET end_time = ?,
                    raw_event_count = raw_event_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (occurred_at, existing["id"]),
            )
            row = conn.execute(
                "SELECT * FROM behavior_sessions WHERE id = ?", (existing["id"],)
            ).fetchone()
            return {"session": _row_to_dict(row), "is_new_session": False}

        cursor = conn.execute(
            """
            INSERT INTO behavior_sessions (
                pet_id,
                behavior,
                location_name,
                start_time,
                end_time,
                raw_event_count,
                status
            )
            VALUES (?, ?, ?, ?, ?, 1, 'active')
            """,
            (pet_id, behavior, location_name, occurred_at, occurred_at),
        )
        session_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM behavior_sessions WHERE id = ?", (session_id,)
        ).fetchone()

    return {"session": _row_to_dict(row), "is_new_session": True}


def _minutes_between(start: str, end: str) -> int:
    start_dt = _parse_iso_datetime(start)
    end_dt = _parse_iso_datetime(end)
    return int((end_dt - start_dt).total_seconds() // 60)


def _record_anomaly(
    conn: sqlite3.Connection,
    pet_id: int,
    event_id: int,
    anomaly_type: str,
    description: str,
) -> dict[str, Any]:
    cursor = conn.execute(
        """
        INSERT INTO anomalies (
            pet_id,
            event_id,
            anomaly_type,
            description
        )
        VALUES (?, ?, ?, ?)
        """,
        (pet_id, event_id, anomaly_type, description),
    )
    anomaly_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM anomalies WHERE id = ?", (anomaly_id,)).fetchone()
    return _row_to_dict(row)


def handle_sleep_event(
    event: dict[str, Any],
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """
    Apply sleep_start/sleep_end state machine rules.

    Returns:
        {
            "sleep_session": {...} | None,
            "anomaly": {...} | None,
            "action": "started" | "completed" | "ignored" | "anomaly"
        }
    """
    behavior = event["behavior"]
    if behavior not in {"sleep_start", "sleep_end"}:
        raise ValueError("handle_sleep_event only supports sleep_start and sleep_end")
    if event["status"] != "confirmed":
        return {"sleep_session": None, "anomaly": None, "action": "ignored"}

    pet_id = event["pet_id"]
    event_id = event["id"]
    occurred_at = event["occurred_at"]

    with connect(db_path) as conn:
        active = conn.execute(
            """
            SELECT *
            FROM sleep_sessions
            WHERE pet_id = ?
              AND status = 'active'
            ORDER BY start_time DESC, id DESC
            LIMIT 1
            """,
            (pet_id,),
        ).fetchone()

        if behavior == "sleep_start":
            if active:
                anomaly = _record_anomaly(
                    conn,
                    pet_id,
                    event_id,
                    "duplicate_sleep_start",
                    "Received sleep_start while an active sleep session already exists.",
                )
                return {
                    "sleep_session": _row_to_dict(active),
                    "anomaly": anomaly,
                    "action": "anomaly",
                }

            cursor = conn.execute(
                """
                INSERT INTO sleep_sessions (
                    pet_id,
                    start_event_id,
                    start_time,
                    status
                )
                VALUES (?, ?, ?, 'active')
                """,
                (pet_id, event_id, occurred_at),
            )
            sleep_session_id = cursor.lastrowid
            row = conn.execute(
                "SELECT * FROM sleep_sessions WHERE id = ?", (sleep_session_id,)
            ).fetchone()
            return {
                "sleep_session": _row_to_dict(row),
                "anomaly": None,
                "action": "started",
            }

        if active is None:
            anomaly = _record_anomaly(
                conn,
                pet_id,
                event_id,
                "orphan_sleep_end",
                "Received sleep_end without an active sleep session.",
            )
            return {"sleep_session": None, "anomaly": anomaly, "action": "anomaly"}

        duration_minutes = _minutes_between(active["start_time"], occurred_at)
        if duration_minutes < 0:
            anomaly = _record_anomaly(
                conn,
                pet_id,
                event_id,
                "sleep_end_before_start",
                "Received sleep_end earlier than the active sleep_start.",
            )
            return {
                "sleep_session": _row_to_dict(active),
                "anomaly": anomaly,
                "action": "anomaly",
            }

        conn.execute(
            """
            UPDATE sleep_sessions
            SET end_event_id = ?,
                end_time = ?,
                duration_minutes = ?,
                status = 'completed',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (event_id, occurred_at, duration_minutes, active["id"]),
        )
        row = conn.execute(
            "SELECT * FROM sleep_sessions WHERE id = ?", (active["id"],)
        ).fetchone()
        return {
            "sleep_session": _row_to_dict(row),
            "anomaly": None,
            "action": "completed",
        }


def _parse_date(value: Optional[str]) -> date:
    if value is None:
        return datetime.now().date()
    return date.fromisoformat(value)


def _range_dates(range_type: str, end_date: Optional[str]) -> list[date]:
    if range_type not in {"day", "week", "month"}:
        raise ValueError("range_type must be one of ['day', 'week', 'month']")

    days = {"day": 1, "week": 7, "month": 30}[range_type]
    end = _parse_date(end_date)
    start = end - timedelta(days=days - 1)
    return [start + timedelta(days=i) for i in range(days)]


def _day_bounds(day: date) -> tuple[str, str]:
    start = datetime.combine(day, time.min).isoformat()
    end = datetime.combine(day + timedelta(days=1), time.min).isoformat()
    return start, end


def _overlap_minutes(start: str, end: str, day: date) -> int:
    session_start = _parse_iso_datetime(start)
    session_end = _parse_iso_datetime(end)
    day_start = datetime.combine(day, time.min, tzinfo=session_start.tzinfo)
    day_end = day_start + timedelta(days=1)

    overlap_start = max(session_start, day_start)
    overlap_end = min(session_end, day_end)
    if overlap_end <= overlap_start:
        return 0
    return int((overlap_end - overlap_start).total_seconds() // 60)


def get_pet_stats(
    pet_id: int,
    range_type: str,
    end_date: Optional[str] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Return JSON-ready behavior and sleep stats for day/week/month ranges."""
    days = _range_dates(range_type, end_date)
    range_start, _ = _day_bounds(days[0])
    _, range_end = _day_bounds(days[-1])

    daily = {
        day.isoformat(): {
            "date": day.isoformat(),
            "eat_count": 0,
            "drink_count": 0,
            "poop_count": 0,
            "play_count": 0,
            "sleep_minutes": 0,
        }
        for day in days
    }

    with connect(db_path) as conn:
        pet = conn.execute("SELECT id FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if pet is None:
            raise ValueError(f"pet_id {pet_id} does not exist")

        behavior_rows = conn.execute(
            """
            SELECT behavior, start_time
            FROM behavior_sessions
            WHERE pet_id = ?
              AND status = 'active'
              AND start_time >= ?
              AND start_time < ?
            """,
            (pet_id, range_start, range_end),
        ).fetchall()

        sleep_rows = conn.execute(
            """
            SELECT start_time, end_time
            FROM sleep_sessions
            WHERE pet_id = ?
              AND status = 'completed'
              AND end_time IS NOT NULL
              AND start_time < ?
              AND end_time >= ?
            """,
            (pet_id, range_end, range_start),
        ).fetchall()

    for row in behavior_rows:
        day_key = _parse_iso_datetime(row["start_time"]).date().isoformat()
        if day_key in daily:
            daily[day_key][f"{row['behavior']}_count"] += 1

    for row in sleep_rows:
        for day in days:
            daily[day.isoformat()]["sleep_minutes"] += _overlap_minutes(
                row["start_time"],
                row["end_time"],
                day,
            )

    day_values = [daily[day.isoformat()] for day in days]
    totals = {
        "eat_count": sum(item["eat_count"] for item in day_values),
        "drink_count": sum(item["drink_count"] for item in day_values),
        "poop_count": sum(item["poop_count"] for item in day_values),
        "play_count": sum(item["play_count"] for item in day_values),
        "sleep_minutes": sum(item["sleep_minutes"] for item in day_values),
    }

    return {
        "pet_id": pet_id,
        "range": range_type,
        "start_date": days[0].isoformat(),
        "end_date": days[-1].isoformat(),
        "days": day_values,
        "totals": totals,
    }


def save_event_message(
    pet_id: int,
    message: str,
    severity: str,
    facts_used: list[str],
    model_name: str,
    prompt_version: str,
    event_id: Optional[int] = None,
    session_id: Optional[int] = None,
    internal_signal: Optional[str] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Persist one generated event message."""
    if severity not in {"normal", "info", "warning"}:
        raise ValueError("severity must be one of ['normal', 'info', 'warning']")
    if not message.strip():
        raise ValueError("message is required")

    facts_used_json = json.dumps(facts_used, ensure_ascii=False)

    with connect(db_path) as conn:
        pet = conn.execute("SELECT id FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if pet is None:
            raise ValueError(f"pet_id {pet_id} does not exist")

        cursor = conn.execute(
            """
            INSERT INTO event_messages (
                event_id,
                session_id,
                pet_id,
                message,
                severity,
                facts_used_json,
                internal_signal,
                model_name,
                prompt_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                session_id,
                pet_id,
                message,
                severity,
                facts_used_json,
                internal_signal,
                model_name,
                prompt_version,
            ),
        )
        message_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM event_messages WHERE id = ?", (message_id,)
        ).fetchone()

    return _row_to_dict(row)


def save_summary(
    pet_id: int,
    range_type: str,
    start_date: str,
    end_date: str,
    stats: dict[str, Any],
    summary: dict[str, Any],
    model_name: str,
    prompt_version: str,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Persist one generated day/week/month summary."""
    if range_type not in {"day", "week", "month"}:
        raise ValueError("range_type must be one of ['day', 'week', 'month']")

    stats_json = json.dumps(stats, ensure_ascii=False)
    summary_json = json.dumps(summary, ensure_ascii=False)

    with connect(db_path) as conn:
        pet = conn.execute("SELECT id FROM pets WHERE id = ?", (pet_id,)).fetchone()
        if pet is None:
            raise ValueError(f"pet_id {pet_id} does not exist")

        cursor = conn.execute(
            """
            INSERT INTO summaries (
                pet_id,
                range_type,
                start_date,
                end_date,
                stats_json,
                summary_json,
                model_name,
                prompt_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                pet_id,
                range_type,
                start_date,
                end_date,
                stats_json,
                summary_json,
                model_name,
                prompt_version,
            ),
        )
        summary_id = cursor.lastrowid
        row = conn.execute(
            "SELECT * FROM summaries WHERE id = ?", (summary_id,)
        ).fetchone()

    return _row_to_dict(row)


if __name__ == "__main__":
    path = init_db()
    print(f"Initialized SQLite database at {path}")
