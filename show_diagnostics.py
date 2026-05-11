"""Print recent structured diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


LOG_PATH = Path("logs/pet_agent_diagnostics.jsonl")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show recent pet agent diagnostics.")
    parser.add_argument("--trace-id", default="", help="Filter by trace id.")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    if not LOG_PATH.exists():
        print("No diagnostics log yet.")
        return

    rows = []
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if args.trace_id and item.get("trace_id") != args.trace_id:
            continue
        rows.append(item)

    for item in rows[-args.limit :]:
        print(json.dumps(item, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
