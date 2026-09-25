#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

CORE10_ID = "WAT-core10-final-v1"
CORE13_ID = "WAT-core13-observation-v1"
ADDED = [
    ("000977.SZ", "浪潮信息"),
    ("000938.SZ", "紫光股份"),
    ("000063.SZ", "中兴通讯"),
]
EFFECTIVE_TRADE_DATE = "2026-09-28"

def main() -> None:
    dsn = os.environ["NEON_DATABASE_URL"]
    now = datetime.now(timezone.utc).isoformat()

    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=15) as conn:
        with conn.cursor() as cur:
            cur.execute("BEGIN")
            cur.execute(
                "SELECT count(*) AS n FROM watchlist_items WHERE watchlist_id=%s",
                (CORE10_ID,),
            )
            core10_before = cur.fetchone()["n"]
            if core10_before != 10:
                raise RuntimeError(f"Core10 invariant failed before patch: expected 10, got {core10_before}")

            cur.execute(
                """
                INSERT INTO watchlists(id,name,description,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT(id) DO UPDATE
                SET name=EXCLUDED.name,
                    description=EXCLUDED.description,
                    updated_at=EXCLUDED.updated_at
                """,
                (
                    CORE13_ID,
                    "Core13 Daily Observation",
                    "Core10 frozen baseline plus 000977.SZ/000938.SZ/000063.SZ for prospective DAILY_OBSERVATION_SHADOW only. Does not replace or redefine WAT-core10-final-v1.",
                    now,
                    now,
                ),
            )

            cur.execute(
                """
                INSERT INTO watchlist_items(
                    watchlist_id,symbol,display_name,thesis_id,status,
                    monitoring_cadence,metadata_json,added_at,updated_at
                )
                SELECT
                    %s,symbol,display_name,thesis_id,status,
                    monitoring_cadence,metadata_json,%s,%s
                FROM watchlist_items
                WHERE watchlist_id=%s
                ON CONFLICT(watchlist_id,symbol) DO UPDATE
                SET display_name=EXCLUDED.display_name,
                    thesis_id=EXCLUDED.thesis_id,
                    status=EXCLUDED.status,
                    monitoring_cadence=EXCLUDED.monitoring_cadence,
                    metadata_json=EXCLUDED.metadata_json,
                    updated_at=EXCLUDED.updated_at
                """,
                (CORE13_ID, now, now, CORE10_ID),
            )

            for symbol, name in ADDED:
                metadata = json.dumps(
                    {
                        "role": "DAILY_OBSERVATION_SHADOW",
                        "core10_member": False,
                        "enters_core10_cross_sectional_ranking": False,
                        "retrospective_live_shadow_backfill_allowed": False,
                        "prospective_effective_trade_date": EFFECTIVE_TRADE_DATE,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                cur.execute(
                    """
                    INSERT INTO watchlist_items(
                        watchlist_id,symbol,display_name,thesis_id,status,
                        monitoring_cadence,metadata_json,added_at,updated_at
                    )
                    VALUES (%s,%s,%s,NULL,'ACTIVE','DAILY',%s,%s,%s)
                    ON CONFLICT(watchlist_id,symbol) DO UPDATE
                    SET display_name=EXCLUDED.display_name,
                        status='ACTIVE',
                        monitoring_cadence='DAILY',
                        metadata_json=EXCLUDED.metadata_json,
                        updated_at=EXCLUDED.updated_at
                    """,
                    (CORE13_ID, symbol, name, metadata, now, now),
                )

            cur.execute("SELECT count(*) AS n FROM watchlist_items WHERE watchlist_id=%s", (CORE13_ID,))
            core13_count = cur.fetchone()["n"]
            cur.execute(
                "SELECT count(*) AS n FROM watchlist_items WHERE watchlist_id=%s AND symbol=ANY(%s)",
                (CORE13_ID, [x[0] for x in ADDED]),
            )
            added_count = cur.fetchone()["n"]
            cur.execute("SELECT count(*) AS n FROM watchlist_items WHERE watchlist_id=%s", (CORE10_ID,))
            core10_after = cur.fetchone()["n"]

            if core13_count != 13 or added_count != 3 or core10_after != 10:
                raise RuntimeError(
                    f"Post-patch invariant failed: core13={core13_count}, added={added_count}, core10={core10_after}"
                )

            conn.commit()

    print("CORE13_RUNTIME_PATCH_PASS")
    print(f"core10_count={core10_after}")
    print(f"core13_count={core13_count}")
    print(f"added_observation_count={added_count}")
    print(f"prospective_effective_trade_date={EFFECTIVE_TRADE_DATE}")

if __name__ == "__main__":
    main()
