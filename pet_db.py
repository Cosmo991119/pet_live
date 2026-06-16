"""
SQLite persistence layer for the pet agent.

This module owns the structured fact store. LLM-generated text should depend on
data stored here, but factual state changes should not depend on the LLM.
"""

from pathlib import Path
from datetime import date, datetime, time, timedelta
import json
import os
import secrets
import sqlite3
from typing import Any, Optional, Union


DB_PATH = Path("pet_agent.db")
ALLOWED_PET_MODES = {"real", "virtual"}
ALLOWED_SPECIES = {"cat", "dog", "other"}
ALLOWED_PERSONALITIES = {"sweet", "cool", "energetic", "gentle"}
ALLOWED_BEHAVIORS = {"eat", "drink", "poop", "play", "sleep_start", "sleep_end"}
SESSION_BEHAVIORS = {"eat", "drink", "poop", "play"}
ALLOWED_RELATIONSHIP_LABELS = {
    "often_replies_to_target",
    "likes_staying_near_target",
    "quiet_around_target",
    "pulls_target_to_play",
    "keeps_distance_from_target",
}
ALLOWED_MEMORY_TYPES = {
    "owner_shared",
    "co_experienced",
    "pet_milestone",
    "work_companion",
}
ALLOWED_MEMORY_SOURCES = {
    "manual",
    "telegram",
    "desktop",
    "event",
    "summary",
    "assistant",
}
ALLOWED_MEMORY_VISIBILITIES = {"home", "private"}
ALLOWED_MEMORY_USE_CLASSES = {"recallable", "behavioral", "private"}
ALLOWED_MEMORY_RECALL_POLICIES = {"normal", "owner_asked_only"}
ALLOWED_MEMORY_PARTICIPANT_ROLES = {
    "participant",
    "shared_with",
    "mentioned_only",
    "subject",
    "helper",
}
MEMORY_PARTICIPANT_ROLES = {
    "owner_shared": "shared_with",
    "co_experienced": "participant",
    "pet_milestone": "subject",
    "work_companion": "helper",
}
MEMORY_RECALL_GUIDANCE = {
    "owner_shared": (
        "Pets may recall that the owner shared this moment with them, "
        "but must not claim physical presence."
    ),
    "co_experienced": (
        "Only participant pets may recall this as a lived shared experience; "
        "non-participants may only know it was discussed."
    ),
    "pet_milestone": (
        "Recall as a pet state or growth milestone grounded in product facts."
    ),
    "work_companion": (
        "Recall as a work-help moment; avoid storing or repeating secrets."
    ),
}
ALLOWED_ASSISTANT_ITEM_TYPES = {"note", "todo", "alarm", "focus"}
ALLOWED_ASSISTANT_ITEM_STATUSES = {"open", "done", "dismissed"}
ALLOWED_ASSISTANT_ITEM_SOURCES = {"manual", "telegram", "desktop", "assistant"}
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


def _migrate_memory_participant_roles(conn: sqlite3.Connection) -> None:
    """Upgrade older databases whose participant role CHECK omits mentioned_only."""
    participant_sql = _table_sql(conn, "pet_memory_participants")
    if not participant_sql or "'mentioned_only'" in participant_sql:
        return

    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        ALTER TABLE pet_memory_participants RENAME TO pet_memory_participants_old;

        CREATE TABLE pet_memory_participants (
            memory_id INTEGER NOT NULL,
            pet_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (
                role IN (
                    'shared_with',
                    'participant',
                    'mentioned_only',
                    'subject',
                    'helper'
                )
            ),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (memory_id, pet_id),
            FOREIGN KEY (memory_id) REFERENCES pet_memories(id) ON DELETE CASCADE,
            FOREIGN KEY (pet_id) REFERENCES pets(id)
        );

        INSERT INTO pet_memory_participants (
            memory_id,
            pet_id,
            role,
            created_at
        )
        SELECT
            memory_id,
            pet_id,
            role,
            created_at
        FROM pet_memory_participants_old;

        DROP TABLE pet_memory_participants_old;

        CREATE INDEX IF NOT EXISTS idx_pet_memory_participants_pet
        ON pet_memory_participants (pet_id, memory_id);
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def init_db(db_path: DbPath = DB_PATH) -> Path:
    """Create all pet agent tables if they do not already exist."""
    db_path = Path(db_path)
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS owners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_chat_id TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
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
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES owners(id)
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

            CREATE TABLE IF NOT EXISTS assistant_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                pet_id INTEGER,
                item_type TEXT NOT NULL CHECK (
                    item_type IN ('note', 'todo', 'alarm', 'focus')
                ),
                title TEXT NOT NULL,
                body TEXT NOT NULL DEFAULT '',
                due_at TEXT,
                duration_minutes INTEGER CHECK (
                    duration_minutes IS NULL OR duration_minutes > 0
                ),
                status TEXT NOT NULL DEFAULT 'open' CHECK (
                    status IN ('open', 'done', 'dismissed')
                ),
                source TEXT NOT NULL DEFAULT 'manual' CHECK (
                    source IN ('manual', 'telegram', 'desktop', 'assistant')
                ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                FOREIGN KEY (owner_id) REFERENCES owners(id),
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_assistant_items_owner_status_due
            ON assistant_items (owner_id, status, due_at);

            CREATE INDEX IF NOT EXISTS idx_assistant_items_owner_type_created
            ON assistant_items (owner_id, item_type, created_at);

            CREATE TABLE IF NOT EXISTS pet_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_pet_id INTEGER NOT NULL,
                to_pet_id INTEGER NOT NULL,
                labels_json TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                muted INTEGER NOT NULL DEFAULT 0 CHECK (muted IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (from_pet_id != to_pet_id),
                UNIQUE (from_pet_id, to_pet_id),
                FOREIGN KEY (from_pet_id) REFERENCES pets(id),
                FOREIGN KEY (to_pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pet_relationships_from_pet
            ON pet_relationships (from_pet_id);

            CREATE INDEX IF NOT EXISTS idx_pet_relationships_to_pet
            ON pet_relationships (to_pet_id);

            CREATE TABLE IF NOT EXISTS pet_friendship_invites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT NOT NULL UNIQUE,
                inviter_owner_id INTEGER NOT NULL,
                inviter_pet_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (
                    status IN ('pending', 'accepted', 'expired', 'cancelled')
                ),
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (inviter_owner_id) REFERENCES owners(id),
                FOREIGN KEY (inviter_pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pet_friendship_invites_owner
            ON pet_friendship_invites (inviter_owner_id, status);

            CREATE TABLE IF NOT EXISTS pet_friendships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_a_id INTEGER NOT NULL,
                pet_b_id INTEGER NOT NULL,
                owner_a_id INTEGER NOT NULL,
                owner_b_id INTEGER NOT NULL,
                affinity INTEGER NOT NULL DEFAULT 50 CHECK (
                    affinity >= 0 AND affinity <= 100
                ),
                status TEXT NOT NULL DEFAULT 'active' CHECK (
                    status IN ('active', 'blocked')
                ),
                muted INTEGER NOT NULL DEFAULT 0 CHECK (muted IN (0, 1)),
                created_from_invite_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (pet_a_id != pet_b_id),
                CHECK (owner_a_id != owner_b_id),
                UNIQUE (pet_a_id, pet_b_id),
                FOREIGN KEY (pet_a_id) REFERENCES pets(id),
                FOREIGN KEY (pet_b_id) REFERENCES pets(id),
                FOREIGN KEY (owner_a_id) REFERENCES owners(id),
                FOREIGN KEY (owner_b_id) REFERENCES owners(id),
                FOREIGN KEY (created_from_invite_id) REFERENCES pet_friendship_invites(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pet_friendships_owner_a
            ON pet_friendships (owner_a_id, status);

            CREATE INDEX IF NOT EXISTS idx_pet_friendships_owner_b
            ON pet_friendships (owner_b_id, status);

            CREATE TABLE IF NOT EXISTS pet_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL CHECK (
                    memory_type IN (
                        'owner_shared',
                        'co_experienced',
                        'pet_milestone',
                        'work_companion'
                    )
                ),
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL,
                source TEXT NOT NULL CHECK (
                    source IN (
                        'manual',
                        'telegram',
                        'desktop',
                        'event',
                        'summary',
                        'assistant'
                    )
                ),
                emotional_tone TEXT NOT NULL DEFAULT '',
                importance INTEGER NOT NULL DEFAULT 3 CHECK (
                    importance >= 1 AND importance <= 5
                ),
                visibility TEXT NOT NULL DEFAULT 'home' CHECK (
                    visibility IN ('home', 'private')
                ),
                use_class TEXT NOT NULL DEFAULT 'recallable' CHECK (
                    use_class IN ('recallable', 'behavioral', 'private')
                ),
                recall_policy TEXT NOT NULL DEFAULT 'normal' CHECK (
                    recall_policy IN ('normal', 'owner_asked_only')
                ),
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_pet_memories_type_created
            ON pet_memories (memory_type, created_at);

            CREATE TABLE IF NOT EXISTS pet_memory_participants (
                memory_id INTEGER NOT NULL,
                pet_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (
                    role IN (
                        'shared_with',
                        'participant',
                        'mentioned_only',
                        'subject',
                        'helper'
                    )
                ),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (memory_id, pet_id),
                FOREIGN KEY (memory_id) REFERENCES pet_memories(id) ON DELETE CASCADE,
                FOREIGN KEY (pet_id) REFERENCES pets(id)
            );

            CREATE INDEX IF NOT EXISTS idx_pet_memory_participants_pet
            ON pet_memory_participants (pet_id, memory_id);
            """
        )
        if not _column_exists(conn, "pets", "pet_mode"):
            conn.execute(
                "ALTER TABLE pets ADD COLUMN pet_mode TEXT NOT NULL DEFAULT 'real'"
            )
        if not _column_exists(conn, "pets", "owner_id"):
            conn.execute("ALTER TABLE pets ADD COLUMN owner_id INTEGER")
        if not _column_exists(conn, "pet_memories", "use_class"):
            conn.execute(
                "ALTER TABLE pet_memories ADD COLUMN use_class TEXT NOT NULL DEFAULT 'recallable'"
            )
        if not _column_exists(conn, "pet_memories", "recall_policy"):
            conn.execute(
                "ALTER TABLE pet_memories ADD COLUMN recall_policy TEXT NOT NULL DEFAULT 'normal'"
            )
        _assign_existing_pets_to_default_owner(conn)
        _migrate_play_behavior(conn)
        _migrate_memory_participant_roles(conn)
    return db_path


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _default_owner_chat_id() -> str:
    return (
        os.getenv("TELEGRAM_DEFAULT_OWNER_CHAT_ID")
        or os.getenv("TELEGRAM_CHAT_ID")
        or "__default_owner__"
    )


def _default_owner_display_name() -> str:
    return os.getenv("TELEGRAM_DEFAULT_OWNER_DISPLAY_NAME") or "Default Owner"


def _ensure_owner_for_telegram_chat(
    conn: sqlite3.Connection,
    telegram_chat_id: str,
    display_name: str = "",
) -> dict[str, Any]:
    chat_id = str(telegram_chat_id).strip()
    if not chat_id:
        raise ValueError("telegram_chat_id is required")
    name = str(display_name or "").strip()
    conn.execute(
        """
        INSERT INTO owners (telegram_chat_id, display_name, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(telegram_chat_id) DO UPDATE SET
            display_name = CASE
                WHEN excluded.display_name != '' THEN excluded.display_name
                ELSE owners.display_name
            END,
            updated_at = CURRENT_TIMESTAMP
        """,
        (chat_id, name),
    )
    row = conn.execute(
        "SELECT * FROM owners WHERE telegram_chat_id = ?",
        (chat_id,),
    ).fetchone()
    return _row_to_dict(row)


def _assign_existing_pets_to_default_owner(conn: sqlite3.Connection) -> None:
    default_owner = _ensure_owner_for_telegram_chat(
        conn,
        _default_owner_chat_id(),
        _default_owner_display_name(),
    )
    conn.execute(
        "UPDATE pets SET owner_id = ? WHERE owner_id IS NULL",
        (default_owner["id"],),
    )


def create_owner_for_telegram_chat(
    telegram_chat_id: str,
    display_name: str = "",
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Create or update an owner identified by Telegram chat id."""
    with connect(db_path) as conn:
        return _ensure_owner_for_telegram_chat(conn, telegram_chat_id, display_name)


def get_owner_by_telegram_chat(
    telegram_chat_id: str,
    db_path: DbPath = DB_PATH,
) -> Optional[dict[str, Any]]:
    """Return an owner by Telegram chat id, or None if missing."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM owners WHERE telegram_chat_id = ?",
            (str(telegram_chat_id),),
        ).fetchone()
    return _row_to_dict(row) if row else None


def _resolve_owner_id(conn: sqlite3.Connection, owner_id: Optional[int]) -> int:
    if owner_id is None:
        owner = _ensure_owner_for_telegram_chat(
            conn,
            _default_owner_chat_id(),
            _default_owner_display_name(),
        )
        return int(owner["id"])
    owner = conn.execute("SELECT id FROM owners WHERE id = ?", (owner_id,)).fetchone()
    if owner is None:
        raise ValueError(f"owner_id {owner_id} does not exist")
    return int(owner["id"])


def _normalize_relationship_labels(labels: list[str]) -> list[str]:
    normalized: list[str] = []
    for label in labels:
        value = str(label).strip()
        if not value:
            continue
        if value not in ALLOWED_RELATIONSHIP_LABELS:
            raise ValueError(
                f"relationship label must be one of {sorted(ALLOWED_RELATIONSHIP_LABELS)}"
            )
        if value not in normalized:
            normalized.append(value)
    return normalized


def _relationship_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = _row_to_dict(row)
    data["labels"] = json.loads(data.get("labels_json") or "[]")
    data["muted"] = bool(data["muted"])
    return data


def _friendship_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    data = _row_to_dict(row)
    if "muted" in data:
        data["muted"] = bool(data["muted"])
    return data


def _ensure_pet_exists(conn: sqlite3.Connection, pet_id: int, field_name: str) -> None:
    pet = conn.execute("SELECT id FROM pets WHERE id = ?", (pet_id,)).fetchone()
    if pet is None:
        raise ValueError(f"{field_name} {pet_id} does not exist")


def _pet_owner_id(conn: sqlite3.Connection, pet_id: int, field_name: str) -> int:
    row = conn.execute(
        "SELECT owner_id FROM pets WHERE id = ?",
        (pet_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"{field_name} {pet_id} does not exist")
    return int(row["owner_id"])


def _ordered_friendship_pair(
    first_pet_id: int,
    first_owner_id: int,
    second_pet_id: int,
    second_owner_id: int,
) -> tuple[int, int, int, int]:
    if int(first_pet_id) <= int(second_pet_id):
        return int(first_pet_id), int(second_pet_id), int(first_owner_id), int(second_owner_id)
    return int(second_pet_id), int(first_pet_id), int(second_owner_id), int(first_owner_id)


def create_pet(
    name: str,
    species: str,
    personality: str,
    owner_call_name: str,
    pet_mode: str = "real",
    profile: Optional[dict[str, Any]] = None,
    owner_id: Optional[int] = None,
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
        resolved_owner_id = _resolve_owner_id(conn, owner_id)
        cursor = conn.execute(
            """
            INSERT INTO pets (
                owner_id,
                name,
                pet_mode,
                species,
                personality,
                owner_call_name,
                profile_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_owner_id,
                name,
                pet_mode,
                species,
                personality,
                owner_call_name,
                profile_json,
            ),
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
    owner_id: Optional[int] = None,
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
        clauses = ["id = ?"]
        lookup_params: list[Any] = [pet_id]
        if owner_id is not None:
            clauses.append("owner_id = ?")
            lookup_params.append(owner_id)
        pet = conn.execute(
            f"SELECT id FROM pets WHERE {' AND '.join(clauses)}",
            lookup_params,
        ).fetchone()
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


def delete_pet(
    pet_id: int,
    owner_id: Optional[int] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Delete one pet and local dependent demo data."""
    with connect(db_path) as conn:
        clauses = ["id = ?"]
        lookup_params: list[Any] = [pet_id]
        if owner_id is not None:
            clauses.append("owner_id = ?")
            lookup_params.append(owner_id)
        row = conn.execute(
            f"SELECT * FROM pets WHERE {' AND '.join(clauses)}",
            lookup_params,
        ).fetchone()
        if row is None:
            raise ValueError(f"pet_id {pet_id} does not exist")

        pet = _row_to_dict(row)
        conn.execute("DELETE FROM event_messages WHERE pet_id = ?", (pet_id,))
        conn.execute("DELETE FROM summaries WHERE pet_id = ?", (pet_id,))
        conn.execute("DELETE FROM anomalies WHERE pet_id = ?", (pet_id,))
        conn.execute("DELETE FROM sleep_sessions WHERE pet_id = ?", (pet_id,))
        conn.execute("DELETE FROM behavior_sessions WHERE pet_id = ?", (pet_id,))
        conn.execute("DELETE FROM virtual_pet_states WHERE pet_id = ?", (pet_id,))
        conn.execute("UPDATE assistant_items SET pet_id = NULL WHERE pet_id = ?", (pet_id,))
        conn.execute(
            "DELETE FROM pet_relationships WHERE from_pet_id = ? OR to_pet_id = ?",
            (pet_id, pet_id),
        )
        memory_rows = conn.execute(
            """
            SELECT memory_id
            FROM pet_memory_participants
            WHERE pet_id = ?
            """,
            (pet_id,),
        ).fetchall()
        memory_ids = [row["memory_id"] for row in memory_rows]
        conn.execute("DELETE FROM pet_memory_participants WHERE pet_id = ?", (pet_id,))
        for memory_id in memory_ids:
            remaining = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM pet_memory_participants
                WHERE memory_id = ?
                """,
                (memory_id,),
            ).fetchone()["count"]
            if remaining == 0:
                conn.execute("DELETE FROM pet_memories WHERE id = ?", (memory_id,))
        conn.execute("DELETE FROM archived_events WHERE pet_id = ?", (pet_id,))
        conn.execute("DELETE FROM events WHERE pet_id = ?", (pet_id,))
        conn.execute("DELETE FROM pets WHERE id = ?", (pet_id,))

    return pet


def _normalize_assistant_item_type(item_type: str) -> str:
    value = str(item_type or "").strip()
    if value not in ALLOWED_ASSISTANT_ITEM_TYPES:
        raise ValueError(f"item_type must be one of {sorted(ALLOWED_ASSISTANT_ITEM_TYPES)}")
    return value


def _normalize_assistant_item_status(status: str) -> str:
    value = str(status or "").strip()
    if value not in ALLOWED_ASSISTANT_ITEM_STATUSES:
        raise ValueError(f"status must be one of {sorted(ALLOWED_ASSISTANT_ITEM_STATUSES)}")
    return value


def _normalize_assistant_item_source(source: str) -> str:
    value = str(source or "manual").strip()
    if value not in ALLOWED_ASSISTANT_ITEM_SOURCES:
        raise ValueError(f"source must be one of {sorted(ALLOWED_ASSISTANT_ITEM_SOURCES)}")
    return value


def _validate_optional_iso_datetime(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime") from exc
    return normalized


def _assistant_item_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return _row_to_dict(row)


def create_assistant_item(
    item_type: str,
    title: str,
    body: str = "",
    due_at: Optional[str] = None,
    duration_minutes: Optional[int] = None,
    status: str = "open",
    source: str = "manual",
    owner_id: Optional[int] = None,
    pet_id: Optional[int] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Create a small owner-scoped assistant item such as a note, todo, or alarm."""
    normalized_type = _normalize_assistant_item_type(item_type)
    normalized_status = _normalize_assistant_item_status(status)
    normalized_source = _normalize_assistant_item_source(source)
    title = str(title or "").strip()
    if not title:
        raise ValueError("title is required")
    body = str(body or "").strip()
    normalized_due_at = _validate_optional_iso_datetime(due_at, "due_at")
    if duration_minutes is not None and int(duration_minutes) <= 0:
        raise ValueError("duration_minutes must be positive")

    with connect(db_path) as conn:
        resolved_owner_id = _resolve_owner_id(conn, owner_id)
        if pet_id is not None:
            pet_owner_id = _pet_owner_id(conn, int(pet_id), "pet_id")
            if pet_owner_id != resolved_owner_id:
                raise ValueError("pet_id does not belong to owner_id")
        cursor = conn.execute(
            """
            INSERT INTO assistant_items (
                owner_id,
                pet_id,
                item_type,
                title,
                body,
                due_at,
                duration_minutes,
                status,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_owner_id,
                pet_id,
                normalized_type,
                title,
                body,
                normalized_due_at,
                int(duration_minutes) if duration_minutes is not None else None,
                normalized_status,
                normalized_source,
            ),
        )
        row = conn.execute(
            "SELECT * FROM assistant_items WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return _assistant_item_row_to_dict(row)


def list_assistant_items(
    owner_id: Optional[int] = None,
    item_type: Optional[str] = None,
    status: Optional[str] = "open",
    due_before: Optional[str] = None,
    limit: int = 20,
    db_path: DbPath = DB_PATH,
) -> list[dict[str, Any]]:
    """List assistant items, optionally filtered by owner, type, status, or due time."""
    clauses: list[str] = []
    params: list[Any] = []
    if owner_id is not None:
        clauses.append("owner_id = ?")
        params.append(int(owner_id))
    if item_type is not None:
        clauses.append("item_type = ?")
        params.append(_normalize_assistant_item_type(item_type))
    if status is not None:
        clauses.append("status = ?")
        params.append(_normalize_assistant_item_status(status))
    if due_before is not None:
        clauses.append("due_at IS NOT NULL")
        clauses.append("due_at <= ?")
        params.append(_validate_optional_iso_datetime(due_before, "due_before"))

    limit = max(1, min(100, int(limit)))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM assistant_items
            {where}
            ORDER BY
                CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                due_at ASC,
                created_at DESC,
                id DESC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
    return [_assistant_item_row_to_dict(row) for row in rows]


def complete_assistant_item(
    item_id: int,
    owner_id: Optional[int] = None,
    status: str = "done",
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Mark one assistant item as done or dismissed and return the updated row."""
    normalized_status = _normalize_assistant_item_status(status)
    if normalized_status == "open":
        raise ValueError("complete status must be done or dismissed")
    clauses = ["id = ?"]
    params: list[Any] = [int(item_id)]
    if owner_id is not None:
        clauses.append("owner_id = ?")
        params.append(int(owner_id))

    with connect(db_path) as conn:
        row = conn.execute(
            f"SELECT * FROM assistant_items WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
        if row is None:
            raise ValueError(f"assistant item {item_id} does not exist")
        conn.execute(
            """
            UPDATE assistant_items
            SET status = ?,
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized_status, int(item_id)),
        )
        updated = conn.execute(
            "SELECT * FROM assistant_items WHERE id = ?",
            (int(item_id),),
        ).fetchone()
    return _assistant_item_row_to_dict(updated)


def upsert_pet_relationship(
    from_pet_id: int,
    to_pet_id: int,
    labels: list[str],
    note: str = "",
    muted: bool = False,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Create or update one directed pet relationship edge."""
    if int(from_pet_id) == int(to_pet_id):
        raise ValueError("from_pet_id and to_pet_id must be different")
    normalized_labels = _normalize_relationship_labels(labels)
    labels_json = json.dumps(normalized_labels, ensure_ascii=False)
    note = str(note or "").strip()

    with connect(db_path) as conn:
        _ensure_pet_exists(conn, from_pet_id, "from_pet_id")
        _ensure_pet_exists(conn, to_pet_id, "to_pet_id")
        conn.execute(
            """
            INSERT INTO pet_relationships (
                from_pet_id,
                to_pet_id,
                labels_json,
                note,
                muted,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(from_pet_id, to_pet_id) DO UPDATE SET
                labels_json = excluded.labels_json,
                note = excluded.note,
                muted = excluded.muted,
                updated_at = CURRENT_TIMESTAMP
            """,
            (from_pet_id, to_pet_id, labels_json, note, 1 if muted else 0),
        )
        row = conn.execute(
            """
            SELECT r.*, fp.name AS from_pet_name, tp.name AS to_pet_name
            FROM pet_relationships r
            JOIN pets fp ON fp.id = r.from_pet_id
            JOIN pets tp ON tp.id = r.to_pet_id
            WHERE r.from_pet_id = ? AND r.to_pet_id = ?
            """,
            (from_pet_id, to_pet_id),
        ).fetchone()
    return _relationship_row_to_dict(row)


def get_pet_relationship(
    from_pet_id: int,
    to_pet_id: int,
    db_path: DbPath = DB_PATH,
) -> Optional[dict[str, Any]]:
    """Return one directed relationship edge, or None if missing."""
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT r.*, fp.name AS from_pet_name, tp.name AS to_pet_name
            FROM pet_relationships r
            JOIN pets fp ON fp.id = r.from_pet_id
            JOIN pets tp ON tp.id = r.to_pet_id
            WHERE r.from_pet_id = ? AND r.to_pet_id = ?
            """,
            (from_pet_id, to_pet_id),
        ).fetchone()
    return _relationship_row_to_dict(row) if row else None


def list_pet_relationships(
    pet_id: Optional[int] = None,
    from_pet_id: Optional[int] = None,
    to_pet_id: Optional[int] = None,
    db_path: DbPath = DB_PATH,
) -> list[dict[str, Any]]:
    """List directed relationship edges, optionally filtered by pet."""
    clauses: list[str] = []
    params: list[Any] = []
    if pet_id is not None:
        clauses.append("(r.from_pet_id = ? OR r.to_pet_id = ?)")
        params.extend([pet_id, pet_id])
    if from_pet_id is not None:
        clauses.append("r.from_pet_id = ?")
        params.append(from_pet_id)
    if to_pet_id is not None:
        clauses.append("r.to_pet_id = ?")
        params.append(to_pet_id)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT r.*, fp.name AS from_pet_name, tp.name AS to_pet_name
            FROM pet_relationships r
            JOIN pets fp ON fp.id = r.from_pet_id
            JOIN pets tp ON tp.id = r.to_pet_id
            {where_sql}
            ORDER BY fp.name ASC, tp.name ASC, r.id ASC
            """,
            params,
        ).fetchall()
    return [_relationship_row_to_dict(row) for row in rows]


def set_pet_relationship_muted(
    from_pet_id: int,
    to_pet_id: int,
    muted: bool,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Set the natural-language expression mute flag for one relationship edge."""
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id FROM pet_relationships
            WHERE from_pet_id = ? AND to_pet_id = ?
            """,
            (from_pet_id, to_pet_id),
        ).fetchone()
        if row is None:
            raise ValueError("pet relationship does not exist")
        conn.execute(
            """
            UPDATE pet_relationships
            SET muted = ?, updated_at = CURRENT_TIMESTAMP
            WHERE from_pet_id = ? AND to_pet_id = ?
            """,
            (1 if muted else 0, from_pet_id, to_pet_id),
        )
    relationship = get_pet_relationship(from_pet_id, to_pet_id, db_path=db_path)
    if relationship is None:
        raise ValueError("pet relationship does not exist")
    return relationship


def delete_pet_relationship(
    from_pet_id: int,
    to_pet_id: int,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Hard-delete one directed relationship edge."""
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT r.*, fp.name AS from_pet_name, tp.name AS to_pet_name
            FROM pet_relationships r
            JOIN pets fp ON fp.id = r.from_pet_id
            JOIN pets tp ON tp.id = r.to_pet_id
            WHERE r.from_pet_id = ? AND r.to_pet_id = ?
            """,
            (from_pet_id, to_pet_id),
        ).fetchone()
        if row is None:
            raise ValueError("pet relationship does not exist")
        conn.execute(
            "DELETE FROM pet_relationships WHERE from_pet_id = ? AND to_pet_id = ?",
            (from_pet_id, to_pet_id),
        )
    return _relationship_row_to_dict(row)


def create_pet_friendship_invite(
    inviter_owner_id: int,
    inviter_pet_id: int,
    token: Optional[str] = None,
    expires_at: Optional[str] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Create a short-lived cross-owner pet friendship invite."""
    token_value = str(token or secrets.token_urlsafe(12)).strip()
    if not token_value:
        raise ValueError("token cannot be empty")
    expires = expires_at or (datetime.utcnow() + timedelta(days=7)).isoformat(timespec="seconds")

    with connect(db_path) as conn:
        _resolve_owner_id(conn, int(inviter_owner_id))
        pet_owner_id = _pet_owner_id(conn, int(inviter_pet_id), "inviter_pet_id")
        if pet_owner_id != int(inviter_owner_id):
            raise ValueError("inviter_pet_id does not belong to inviter_owner_id")
        cursor = conn.execute(
            """
            INSERT INTO pet_friendship_invites (
                token,
                inviter_owner_id,
                inviter_pet_id,
                expires_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (token_value, inviter_owner_id, inviter_pet_id, expires),
        )
        row = conn.execute(
            """
            SELECT i.*, p.name AS inviter_pet_name, o.display_name AS inviter_owner_name
            FROM pet_friendship_invites i
            JOIN pets p ON p.id = i.inviter_pet_id
            JOIN owners o ON o.id = i.inviter_owner_id
            WHERE i.id = ?
            """,
            (cursor.lastrowid,),
        ).fetchone()
    return _row_to_dict(row)


def get_pet_friendship_invite(
    token: str,
    db_path: DbPath = DB_PATH,
) -> Optional[dict[str, Any]]:
    """Return one friendship invite by token, or None if missing."""
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT i.*, p.name AS inviter_pet_name, o.display_name AS inviter_owner_name
            FROM pet_friendship_invites i
            JOIN pets p ON p.id = i.inviter_pet_id
            JOIN owners o ON o.id = i.inviter_owner_id
            WHERE i.token = ?
            """,
            (str(token).strip(),),
        ).fetchone()
    return _row_to_dict(row) if row else None


def _friendship_select_sql(where_sql: str = "") -> str:
    return f"""
        SELECT
            f.*,
            pa.name AS pet_a_name,
            pb.name AS pet_b_name,
            oa.display_name AS owner_a_name,
            ob.display_name AS owner_b_name,
            oa.telegram_chat_id AS owner_a_chat_id,
            ob.telegram_chat_id AS owner_b_chat_id,
            i.status AS invite_status
        FROM pet_friendships f
        JOIN pets pa ON pa.id = f.pet_a_id
        JOIN pets pb ON pb.id = f.pet_b_id
        JOIN owners oa ON oa.id = f.owner_a_id
        JOIN owners ob ON ob.id = f.owner_b_id
        LEFT JOIN pet_friendship_invites i ON i.id = f.created_from_invite_id
        {where_sql}
    """


def accept_pet_friendship_invite(
    token: str,
    receiver_owner_id: int,
    receiver_pet_id: int,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Accept a pending invite and create or return the active friendship."""
    token_value = str(token).strip()
    if not token_value:
        raise ValueError("token is required")

    with connect(db_path) as conn:
        invite = conn.execute(
            "SELECT * FROM pet_friendship_invites WHERE token = ?",
            (token_value,),
        ).fetchone()
        if invite is None:
            raise ValueError("friendship invite does not exist")
        if invite["status"] != "pending":
            raise ValueError("friendship invite is not pending")
        expires_at = datetime.fromisoformat(str(invite["expires_at"]))
        if expires_at < datetime.utcnow():
            conn.execute(
                """
                UPDATE pet_friendship_invites
                SET status = 'expired', updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (invite["id"],),
            )
            raise ValueError("friendship invite has expired")

        _resolve_owner_id(conn, int(receiver_owner_id))
        receiver_pet_owner_id = _pet_owner_id(conn, int(receiver_pet_id), "receiver_pet_id")
        if receiver_pet_owner_id != int(receiver_owner_id):
            raise ValueError("receiver_pet_id does not belong to receiver_owner_id")
        inviter_owner_id = int(invite["inviter_owner_id"])
        inviter_pet_id = int(invite["inviter_pet_id"])
        if inviter_owner_id == int(receiver_owner_id):
            raise ValueError("pet friendships require two different owners")
        pet_a_id, pet_b_id, owner_a_id, owner_b_id = _ordered_friendship_pair(
            inviter_pet_id,
            inviter_owner_id,
            int(receiver_pet_id),
            int(receiver_owner_id),
        )
        conn.execute(
            """
            INSERT INTO pet_friendships (
                pet_a_id,
                pet_b_id,
                owner_a_id,
                owner_b_id,
                affinity,
                status,
                muted,
                created_from_invite_id,
                updated_at
            )
            VALUES (?, ?, ?, ?, 50, 'active', 0, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(pet_a_id, pet_b_id) DO UPDATE SET
                status = 'active',
                updated_at = CURRENT_TIMESTAMP
            """,
            (pet_a_id, pet_b_id, owner_a_id, owner_b_id, invite["id"]),
        )
        conn.execute(
            """
            UPDATE pet_friendship_invites
            SET status = 'accepted', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (invite["id"],),
        )
        row = conn.execute(
            _friendship_select_sql("WHERE f.pet_a_id = ? AND f.pet_b_id = ?"),
            (pet_a_id, pet_b_id),
        ).fetchone()
    return _friendship_row_to_dict(row)


def list_pet_friendships(
    owner_id: Optional[int] = None,
    pet_id: Optional[int] = None,
    db_path: DbPath = DB_PATH,
) -> list[dict[str, Any]]:
    """List active cross-owner pet friendships."""
    clauses: list[str] = ["f.status = 'active'"]
    params: list[Any] = []
    if owner_id is not None:
        clauses.append("(f.owner_a_id = ? OR f.owner_b_id = ?)")
        params.extend([owner_id, owner_id])
    if pet_id is not None:
        clauses.append("(f.pet_a_id = ? OR f.pet_b_id = ?)")
        params.extend([pet_id, pet_id])
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(db_path) as conn:
        rows = conn.execute(
            _friendship_select_sql(where_sql)
            + " ORDER BY f.created_at ASC, f.id ASC",
            params,
        ).fetchall()
    return [_friendship_row_to_dict(row) for row in rows]


def _normalize_memory_type(memory_type: str) -> str:
    value = str(memory_type or "").strip()
    if value not in ALLOWED_MEMORY_TYPES:
        raise ValueError(f"memory_type must be one of {sorted(ALLOWED_MEMORY_TYPES)}")
    return value


def _normalize_memory_source(source: str) -> str:
    value = str(source or "manual").strip() or "manual"
    if value not in ALLOWED_MEMORY_SOURCES:
        raise ValueError(f"source must be one of {sorted(ALLOWED_MEMORY_SOURCES)}")
    return value


def _normalize_memory_visibility(visibility: str) -> str:
    value = str(visibility or "home").strip() or "home"
    if value not in ALLOWED_MEMORY_VISIBILITIES:
        raise ValueError(
            f"visibility must be one of {sorted(ALLOWED_MEMORY_VISIBILITIES)}"
        )
    return value


def _normalize_memory_use_class(use_class: str) -> str:
    value = str(use_class or "recallable").strip() or "recallable"
    if value not in ALLOWED_MEMORY_USE_CLASSES:
        raise ValueError(
            f"use_class must be one of {sorted(ALLOWED_MEMORY_USE_CLASSES)}"
        )
    return value


def _normalize_memory_recall_policy(recall_policy: str) -> str:
    value = str(recall_policy or "normal").strip() or "normal"
    if value not in ALLOWED_MEMORY_RECALL_POLICIES:
        raise ValueError(
            f"recall_policy must be one of {sorted(ALLOWED_MEMORY_RECALL_POLICIES)}"
        )
    return value


def _normalize_memory_participant_role(role: str) -> str:
    value = str(role or "").strip()
    if value not in ALLOWED_MEMORY_PARTICIPANT_ROLES:
        raise ValueError(
            f"participant role must be one of {sorted(ALLOWED_MEMORY_PARTICIPANT_ROLES)}"
        )
    return value


def _normalize_memory_participants(
    memory_type: str,
    participant_pet_ids: list[int],
    participants: Optional[list[dict[str, Any]]] = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()
    if participants:
        for participant in participants:
            pet_id = int(participant["pet_id"])
            role = _normalize_memory_participant_role(str(participant.get("role") or ""))
            if pet_id in seen:
                continue
            seen.add(pet_id)
            normalized.append({"pet_id": pet_id, "role": role})
        return normalized

    default_role = MEMORY_PARTICIPANT_ROLES[memory_type]
    for pet_id in _normalize_pet_ids(participant_pet_ids):
        normalized.append({"pet_id": pet_id, "role": default_role})
    return normalized


def _normalize_pet_ids(pet_ids: list[int]) -> list[int]:
    normalized: list[int] = []
    for pet_id in pet_ids:
        value = int(pet_id)
        if value not in normalized:
            normalized.append(value)
    return normalized


def _memory_row_to_dict(
    row: sqlite3.Row,
    participants: list[sqlite3.Row],
) -> dict[str, Any]:
    data = _row_to_dict(row)
    data["metadata"] = json.loads(data.get("metadata_json") or "{}")
    data["participants"] = [
        {
            "pet_id": participant["pet_id"],
            "pet_name": participant["pet_name"],
            "role": participant["role"],
        }
        for participant in participants
    ]
    data["participant_pet_ids"] = [
        participant["pet_id"] for participant in data["participants"]
    ]
    data["recall_guidance"] = MEMORY_RECALL_GUIDANCE[data["memory_type"]]
    return data


def _fetch_pet_memory(
    conn: sqlite3.Connection,
    memory_id: int,
) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM pet_memories WHERE id = ?", (memory_id,)).fetchone()
    if row is None:
        return None
    participants = conn.execute(
        """
        SELECT mp.pet_id, mp.role, p.name AS pet_name
        FROM pet_memory_participants mp
        JOIN pets p ON p.id = mp.pet_id
        WHERE mp.memory_id = ?
        ORDER BY mp.created_at ASC, mp.pet_id ASC
        """,
        (memory_id,),
    ).fetchall()
    return _memory_row_to_dict(row, participants)


def create_pet_memory(
    memory_type: str,
    content: str,
    participant_pet_ids: list[int],
    title: str = "",
    source: str = "manual",
    emotional_tone: str = "",
    importance: int = 3,
    visibility: str = "home",
    use_class: str = "recallable",
    recall_policy: str = "normal",
    participants: Optional[list[dict[str, Any]]] = None,
    metadata: Optional[dict[str, Any]] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Create one durable pet-owner memory with explicit pet participants."""
    memory_type = _normalize_memory_type(memory_type)
    source = _normalize_memory_source(source)
    visibility = _normalize_memory_visibility(visibility)
    use_class = _normalize_memory_use_class(use_class)
    recall_policy = _normalize_memory_recall_policy(recall_policy)
    content = str(content or "").strip()
    if not content:
        raise ValueError("content is required")
    if importance < 1 or importance > 5:
        raise ValueError("importance must be between 1 and 5")

    normalized_participants = _normalize_memory_participants(
        memory_type,
        participant_pet_ids,
        participants,
    )
    if not normalized_participants:
        raise ValueError("participants must include at least one pet")
    metadata_json = json.dumps(metadata or {}, ensure_ascii=False)

    with connect(db_path) as conn:
        for participant in normalized_participants:
            _ensure_pet_exists(conn, participant["pet_id"], "participant_pet_id")

        cursor = conn.execute(
            """
            INSERT INTO pet_memories (
                memory_type,
                title,
                content,
                source,
                emotional_tone,
                importance,
                visibility,
                use_class,
                recall_policy,
                metadata_json,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                memory_type,
                str(title or "").strip(),
                content,
                source,
                str(emotional_tone or "").strip(),
                importance,
                visibility,
                use_class,
                recall_policy,
                metadata_json,
            ),
        )
        memory_id = cursor.lastrowid
        conn.executemany(
            """
            INSERT INTO pet_memory_participants (memory_id, pet_id, role)
            VALUES (?, ?, ?)
            """,
            [
                (memory_id, participant["pet_id"], participant["role"])
                for participant in normalized_participants
            ],
        )
        memory = _fetch_pet_memory(conn, memory_id)
    if memory is None:
        raise RuntimeError("created pet memory could not be loaded")
    return memory


def get_pet_memory(
    memory_id: int,
    db_path: DbPath = DB_PATH,
) -> Optional[dict[str, Any]]:
    """Return one durable pet memory, or None if missing."""
    with connect(db_path) as conn:
        return _fetch_pet_memory(conn, memory_id)


def delete_pet_memory(
    memory_id: int,
    owner_id: Optional[int] = None,
    db_path: DbPath = DB_PATH,
) -> dict[str, Any]:
    """Hard-delete one durable pet memory."""
    with connect(db_path) as conn:
        memory = _fetch_pet_memory(conn, memory_id)
        if memory is None:
            raise ValueError("pet memory does not exist")
        if owner_id is not None:
            resolved_owner_id = _resolve_owner_id(conn, owner_id)
            owned_participant = conn.execute(
                """
                SELECT 1
                FROM pet_memory_participants mp
                JOIN pets p ON p.id = mp.pet_id
                WHERE mp.memory_id = ? AND p.owner_id = ?
                """,
                (memory_id, resolved_owner_id),
            ).fetchone()
            if owned_participant is None:
                raise ValueError("pet memory does not belong to owner_id")
        conn.execute("DELETE FROM pet_memories WHERE id = ?", (memory_id,))
    return memory


def list_pet_memories(
    pet_id: Optional[int] = None,
    memory_type: Optional[str] = None,
    visibility: Optional[str] = None,
    owner_id: Optional[int] = None,
    limit: int = 20,
    db_path: DbPath = DB_PATH,
) -> list[dict[str, Any]]:
    """List recent durable pet memories, optionally filtered by pet and type."""
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")
    clauses: list[str] = []
    params: list[Any] = []
    if memory_type is not None:
        clauses.append("m.memory_type = ?")
        params.append(_normalize_memory_type(memory_type))
    if visibility is not None:
        clauses.append("m.visibility = ?")
        params.append(_normalize_memory_visibility(visibility))
    if pet_id is not None:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM pet_memory_participants mp_filter
                WHERE mp_filter.memory_id = m.id AND mp_filter.pet_id = ?
            )
            """
        )
        params.append(pet_id)
    if owner_id is not None:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM pet_memory_participants mp_owner
                JOIN pets p_owner ON p_owner.id = mp_owner.pet_id
                WHERE mp_owner.memory_id = m.id AND p_owner.owner_id = ?
            )
            """
        )
        params.append(owner_id)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    with connect(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT m.*
            FROM pet_memories m
            {where_sql}
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        memories: list[dict[str, Any]] = []
        for row in rows:
            memory = _fetch_pet_memory(conn, row["id"])
            if memory is not None:
                memories.append(memory)
    return memories


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


def get_pet(
    pet_id: int,
    owner_id: Optional[int] = None,
    db_path: DbPath = DB_PATH,
) -> Optional[dict[str, Any]]:
    """Return one pet by id, or None if it does not exist."""
    with connect(db_path) as conn:
        clauses = ["id = ?"]
        params: list[Any] = [pet_id]
        if owner_id is not None:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        row = conn.execute(
            f"SELECT * FROM pets WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_pets(
    owner_id: Optional[int] = None,
    db_path: DbPath = DB_PATH,
) -> list[dict[str, Any]]:
    """Return pets ordered by creation time, optionally scoped to one owner."""
    with connect(db_path) as conn:
        clauses: list[str] = []
        params: list[Any] = []
        if owner_id is not None:
            clauses.append("owner_id = ?")
            params.append(owner_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM pets {where_sql} ORDER BY created_at ASC, id ASC",
            params,
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
