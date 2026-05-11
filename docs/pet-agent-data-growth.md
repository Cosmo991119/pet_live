# Pet Agent Data Growth Plan

## Scope

The first production pressure point is raw event growth. The app intentionally
keeps every device/virtual-pet event while deriving behavior sessions, sleep
sessions, messages, summaries, and stats from structured tables. That is good
for debugging, but old unreferenced raw events should not grow forever.

## Retention Rule

Default raw event retention is 90 days.

Events older than the retention cutoff are eligible for archival only when they
are not referenced by:

- `event_messages.event_id`
- `sleep_sessions.start_event_id`
- `sleep_sessions.end_event_id`
- `anomalies.event_id`

Referenced events stay in `events` so generated messages, sleep records, and
anomaly investigations remain traceable.

## Archive Strategy

`pet_db.archive_raw_events_before(cutoff, reason="retention_policy")` moves
eligible rows from `events` into `archived_events`, then deletes the originals
from `events`.

The helper supports `dry_run=True` to count eligible rows before changing data.
It is intentionally not wired to automatic startup cleanup, because this repo is
still a local demo and silent deletion would make learning/debugging harder.

Example:

```python
from datetime import datetime, timedelta
from pet_db import archive_raw_events_before

cutoff = (datetime.now() - timedelta(days=90)).isoformat()
result = archive_raw_events_before(cutoff, dry_run=True)
print(result)
```

## Daily Stats Pre-Aggregation

Do not add `daily_stats` yet. Current stats read from `behavior_sessions` and
`sleep_sessions`, not raw `events`, and the supported ranges are day/week/month.
This keeps the implementation simple and transparent for the demo.

Add a `daily_stats` table later when either condition is true:

- stats endpoints become slow with realistic session volume;
- the product needs long-range charts beyond the current day/week/month windows.

Future shape:

```text
daily_stats
- pet_id
- date
- eat_count
- drink_count
- poop_count
- play_count
- sleep_minutes
- generated_at
```

## PostgreSQL Migration Path

When the app moves beyond local SQLite:

1. Introduce a repository/service boundary around the current `pet_db.py`
   functions before changing database engines.
2. Convert SQLite `CHECK` constraints and indexes into PostgreSQL migrations.
3. Store JSON fields as `jsonb` (`profile_json`, `raw_payload`, `stats_json`,
   `summary_json`, virtual pet state).
4. Keep raw events append-only in PostgreSQL and use scheduled jobs for archival.
5. Move `archived_events` to a partition, cold table, or object storage export if
   data volume grows beyond normal relational query needs.
6. Preserve existing API behavior while migrating one table group at a time:
   pets, events/sessions, summaries/messages, virtual pet state.
