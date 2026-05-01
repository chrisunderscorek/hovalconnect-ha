#!/usr/bin/env python3
"""Analyze Home Assistant recorder history for short unavailable states."""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from collections import defaultdict
from pathlib import Path


BAD_STATES = {"unavailable", "unknown"}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (table,),
    ).fetchone()
    return row is not None


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"pragma table_info({table})")}


def build_state_query(conn: sqlite3.Connection, entity_like: list[str], since_ts: float):
    state_columns = columns(conn, "states")
    has_states_meta = table_exists(conn, "states_meta") and "metadata_id" in state_columns

    if "last_updated_ts" in state_columns:
        ts_expr = "s.last_updated_ts"
    elif "last_changed_ts" in state_columns:
        ts_expr = "s.last_changed_ts"
    elif "last_updated" in state_columns:
        ts_expr = "cast(strftime('%s', s.last_updated) as real)"
    else:
        raise SystemExit("Could not find a supported timestamp column in states table.")

    if has_states_meta:
        entity_expr = "m.entity_id"
        join = "join states_meta m on m.metadata_id = s.metadata_id"
    elif "entity_id" in state_columns:
        entity_expr = "s.entity_id"
        join = ""
    else:
        raise SystemExit("Could not find entity_id or states_meta metadata_id mapping.")

    clauses = [f"{ts_expr} >= ?"]
    params: list[str | float] = [since_ts]
    if entity_like:
        clauses.append("(" + " or ".join(f"{entity_expr} like ?" for _ in entity_like) + ")")
        params.extend(entity_like)

    query = f"""
        select {entity_expr} as entity_id, s.state, {ts_expr} as ts
        from states s
        {join}
        where {" and ".join(clauses)}
        order by entity_id, ts
    """
    return query, params


def analyze(rows, short_threshold_seconds: float):
    by_entity: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for entity_id, state, ts in rows:
        if entity_id and state and ts is not None:
            by_entity[str(entity_id)].append((float(ts), str(state)))

    now_ts = time.time()
    entities = {}
    summary = {
        "entities": len(by_entity),
        "rows": 0,
        "unavailable_events": 0,
        "unknown_events": 0,
        "short_unavailable_events": 0,
        "total_bad_seconds": 0.0,
        "max_bad_seconds": 0.0,
    }

    for entity_id, states in by_entity.items():
        entity_stats = {
            "rows": len(states),
            "unavailable_events": 0,
            "unknown_events": 0,
            "short_unavailable_events": 0,
            "total_bad_seconds": 0.0,
            "max_bad_seconds": 0.0,
            "last_bad_state": None,
        }
        summary["rows"] += len(states)

        for index, (ts, state) in enumerate(states):
            if state not in BAD_STATES:
                continue

            next_ts = states[index + 1][0] if index + 1 < len(states) else now_ts
            duration = max(0.0, next_ts - ts)
            entity_stats["total_bad_seconds"] += duration
            entity_stats["max_bad_seconds"] = max(entity_stats["max_bad_seconds"], duration)
            entity_stats["last_bad_state"] = {
                "state": state,
                "start_ts": ts,
                "duration_seconds": round(duration, 3),
            }

            if state == "unavailable":
                entity_stats["unavailable_events"] += 1
                summary["unavailable_events"] += 1
                if duration <= short_threshold_seconds:
                    entity_stats["short_unavailable_events"] += 1
                    summary["short_unavailable_events"] += 1
            elif state == "unknown":
                entity_stats["unknown_events"] += 1
                summary["unknown_events"] += 1

        if entity_stats["unavailable_events"] or entity_stats["unknown_events"]:
            entity_stats["total_bad_seconds"] = round(entity_stats["total_bad_seconds"], 3)
            entity_stats["max_bad_seconds"] = round(entity_stats["max_bad_seconds"], 3)
            entities[entity_id] = entity_stats
            summary["total_bad_seconds"] += entity_stats["total_bad_seconds"]
            summary["max_bad_seconds"] = max(
                summary["max_bad_seconds"],
                entity_stats["max_bad_seconds"],
            )

    summary["total_bad_seconds"] = round(summary["total_bad_seconds"], 3)
    summary["max_bad_seconds"] = round(summary["max_bad_seconds"], 3)
    top_entities = sorted(
        entities.items(),
        key=lambda item: (
            item[1]["unavailable_events"] + item[1]["unknown_events"],
            item[1]["total_bad_seconds"],
        ),
        reverse=True,
    )
    return summary, dict(top_entities)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze HA recorder availability history for Hoval entities.",
    )
    parser.add_argument("database", type=Path, help="Path to a local home-assistant_v2.db copy")
    parser.add_argument(
        "--entity-like",
        action="append",
        default=None,
        help="SQL LIKE pattern for entity_id; repeatable (default: %%hoval%%)",
    )
    parser.add_argument("--days", type=float, default=7.0, help="History window in days")
    parser.add_argument(
        "--short-threshold",
        type=float,
        default=10.0,
        help="Unavailable duration in seconds that counts as short outage",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()
    entity_like = args.entity_like or ["%hoval%"]

    since_ts = time.time() - args.days * 86400
    conn = sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    try:
        query, params = build_state_query(conn, entity_like, since_ts)
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    summary, entities = analyze(rows, args.short_threshold)
    payload = {
        "database": str(args.database),
        "entity_like": entity_like,
        "days": args.days,
        "short_threshold_seconds": args.short_threshold,
        "summary": summary,
        "entities": entities,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
