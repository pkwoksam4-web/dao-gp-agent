#!/usr/bin/env python3
"""Read-only Neon truth bridge for Agent大脑.

Uses NEON_DATABASE_URL from GitHub Actions Secrets.
Never prints the connection string. Runs inside a READ ONLY transaction.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

TARGET_TABLES = [
    "sources",
    "market_bars",
    "market_quotes",
    "capital_flows",
    "stock_feature_snapshots",
    "provider_sync_runs",
    "forecast_runs",
    "forecast_items",
    "live_shadow_run_attestations",
    "shadow_strategy_runs",
    "shadow_observation_snapshots",
    "shadow_maturity_snapshots",
    "settlement_integrity_snapshots",
    "shadow_cohort_snapshots",
    "production_verification_gate_runs",
    "watchlists",
    "watchlist_items",
]

PREFERRED_TIME_COLUMNS = [
    "created_at",
    "finished_at",
    "started_at",
    "snapshot_date",
    "trade_time",
    "as_of",
    "flow_time",
    "anchor_trade_date",
]

DETAIL_TABLES = {
    "sources": 30,
    "stock_feature_snapshots": 30,
    "provider_sync_runs": 30,
    "forecast_runs": 20,
    "forecast_items": 40,
    "live_shadow_run_attestations": 20,
    "shadow_strategy_runs": 20,
    "watchlists": 20,
    "watchlist_items": 100,
}


def fail(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def normalize_dsn(raw: str) -> str:
    """Accept common Neon clipboard formats without exposing the secret."""
    value = raw.strip()
    if not value:
        return value

    # Direct URI, optionally wrapped in an env assignment.
    if value.startswith("DATABASE_URL=") or value.startswith("NEON_DATABASE_URL="):
        value = value.split("=", 1)[1].strip()

    # Extract a PostgreSQL URI from any copied command/text block.
    uri_match = re.search(r"postgres(?:ql)?://[^\s'\"]+", value)
    if uri_match:
        return uri_match.group(0).strip()

    # Standard libpq conninfo: host=... dbname=... user=... password=...
    lowered = value.lower()
    if "host=" in lowered and ("dbname=" in lowered or "database=" in lowered) and "user=" in lowered:
        return value.replace("\\n", " ").strip()

    # Environment-style connection details: PGHOST=..., PGDATABASE=..., etc.
    try:
        tokens = shlex.split(value.replace("\n", " "))
    except ValueError:
        tokens = value.replace("\n", " ").split()

    env_map = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, val = token.split("=", 1)
        if key in {
            "PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD",
            "PGSSLMODE", "PGCHANNELBINDING"
        }:
            env_map[key] = val.strip().strip("'").strip('"')

    if env_map.get("PGHOST") and env_map.get("PGDATABASE") and env_map.get("PGUSER"):
        parts = [
            f"host={env_map['PGHOST']}",
            f"dbname={env_map['PGDATABASE']}",
            f"user={env_map['PGUSER']}",
        ]
        if env_map.get("PGPORT"):
            parts.append(f"port={env_map['PGPORT']}")
        if env_map.get("PGPASSWORD"):
            # libpq quotes single quotes and backslashes with backslashes.
            pw = env_map["PGPASSWORD"].replace("\\\\", "\\\\\\\\").replace("'", "\\'")
            parts.append(f"password='{pw}'")
        if env_map.get("PGSSLMODE"):
            parts.append(f"sslmode={env_map['PGSSLMODE']}")
        if env_map.get("PGCHANNELBINDING"):
            parts.append(f"channel_binding={env_map['PGCHANNELBINDING']}")
        return " ".join(parts)

    return value.strip().strip("'").strip('"')


def main() -> None:
    dsn = normalize_dsn(os.getenv("NEON_DATABASE_URL", ""))
    if not dsn:
        fail("NEON_DATABASE_URL secret is missing.")
    if not (
        dsn.startswith("postgresql://")
        or dsn.startswith("postgres://")
        or ("host=" in dsn.lower() and "user=" in dsn.lower())
    ):
        fail(
            "NEON_DATABASE_URL is present but its format is not recognized. "
            "Use Neon Connect -> Connection string (URI) or standard libpq connection details."
        )

    output_path = Path(os.getenv("NEON_BRIDGE_OUTPUT", "artifacts/neon-truth.json"))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "schema": "agent-brain-neon-sql-bridge/v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": "READ_ONLY",
        "connection_string_exposed": False,
        "database": {},
        "tables": {},
        "details": {},
        "schema_audit": {},
        "table_name_matches": {},
    }

    try:
        with psycopg.connect(
            dsn,
            row_factory=dict_row,
            connect_timeout=15,
            application_name="dao-gp-agent-neon-sql-bridge",
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("BEGIN READ ONLY")
                cur.execute("SET LOCAL statement_timeout = '20s'")

                cur.execute(
                    "SELECT current_database() AS database, current_user AS db_user, "
                    "current_setting('server_version') AS server_version"
                )
                report["database"] = dict(cur.fetchone())

                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                    """
                )
                existing = {r["table_name"] for r in cur.fetchall()}
                report["database"]["public_table_count"] = len(existing)

                for keyword in ["watch", "universe", "symbol", "forecast", "shadow", "source", "feature", "sync"]:
                    report["table_name_matches"][keyword] = sorted(
                        t for t in existing if keyword in t.lower()
                    )

                for table in TARGET_TABLES:
                    if table not in existing:
                        report["tables"][table] = {"exists": False}
                        continue

                    cur.execute(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=%s
                        ORDER BY ordinal_position
                        """,
                        (table,),
                    )
                    columns = [r["column_name"] for r in cur.fetchall()]

                    cur.execute(
                        """
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_schema='public' AND table_name=%s
                        ORDER BY ordinal_position
                        """,
                        (table,),
                    )
                    column_defs = [dict(r) for r in cur.fetchall()]

                    cur.execute(
                        """
                        SELECT tc.constraint_name, tc.constraint_type,
                               array_agg(kcu.column_name ORDER BY kcu.ordinal_position) AS columns
                        FROM information_schema.table_constraints tc
                        LEFT JOIN information_schema.key_column_usage kcu
                          ON tc.constraint_name=kcu.constraint_name
                         AND tc.table_schema=kcu.table_schema
                         AND tc.table_name=kcu.table_name
                        WHERE tc.table_schema='public' AND tc.table_name=%s
                        GROUP BY tc.constraint_name, tc.constraint_type
                        ORDER BY tc.constraint_type, tc.constraint_name
                        """,
                        (table,),
                    )
                    constraints = [dict(r) for r in cur.fetchall()]

                    cur.execute(
                        """
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname='public' AND tablename=%s
                        ORDER BY indexname
                        """,
                        (table,),
                    )
                    indexes = [dict(r) for r in cur.fetchall()]

                    report["schema_audit"][table] = {
                        "columns": column_defs,
                        "constraints": constraints,
                        "indexes": indexes,
                    }

                    cur.execute(
                        sql.SQL("SELECT count(*)::bigint AS n FROM public.{}").format(
                            sql.Identifier(table)
                        )
                    )
                    n = cur.fetchone()["n"]

                    time_col = next((c for c in PREFERRED_TIME_COLUMNS if c in columns), None)
                    max_time = None
                    if time_col:
                        cur.execute(
                            sql.SQL("SELECT max({}) AS max_value FROM public.{}").format(
                                sql.Identifier(time_col), sql.Identifier(table)
                            )
                        )
                        max_time = cur.fetchone()["max_value"]

                    report["tables"][table] = {
                        "exists": True,
                        "row_count": n,
                        "preferred_time_column": time_col,
                        "max_preferred_time": str(max_time) if max_time is not None else None,
                    }

                    if table in DETAIL_TABLES:
                        limit = DETAIL_TABLES[table]
                        order_clause = (
                            sql.SQL(" ORDER BY {} DESC").format(sql.Identifier(time_col))
                            if time_col
                            else sql.SQL("")
                        )
                        q = (
                            sql.SQL("SELECT * FROM public.{}").format(sql.Identifier(table))
                            + order_clause
                            + sql.SQL(" LIMIT {}").format(sql.Literal(limit))
                        )
                        cur.execute(q)
                        rows = cur.fetchall()
                        report["details"][table] = [
                            {k: (str(v) if not isinstance(v, (str, int, float, bool, type(None), dict, list)) else v)
                             for k, v in row.items()}
                            for row in rows
                        ]

                conn.rollback()

    except Exception as exc:
        report["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        fail(f"Neon bridge failed: {type(exc).__name__}: {exc}")

    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("Neon read-only bridge PASS")
    print(f"database={report['database'].get('database')}")
    print(f"public_table_count={report['database'].get('public_table_count')}")
    print("table_name_matches=" + json.dumps(report["table_name_matches"], ensure_ascii=False))
    for table in ["sources","market_bars","market_quotes","capital_flows","stock_feature_snapshots","provider_sync_runs","forecast_runs","forecast_items","shadow_strategy_runs","live_shadow_run_attestations","watchlists","watchlist_items"]:
        audit = report["schema_audit"].get(table, {})
        if audit:
            print("schema_summary[" + table + "]=" + json.dumps({
                "columns": audit.get("columns", []),
                "constraints": audit.get("constraints", []),
                "indexes": audit.get("indexes", []),
            }, ensure_ascii=False, default=str))
    for table in TARGET_TABLES:
        state = report["tables"].get(table, {})
        if state.get("exists"):
            print(
                f"{table}: rows={state.get('row_count')} "
                f"max_{state.get('preferred_time_column')}={state.get('max_preferred_time')}"
            )
        else:
            print(f"{table}: MISSING")


if __name__ == "__main__":
    main()
