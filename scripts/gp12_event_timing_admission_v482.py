from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable


REQUIRED_SOURCE_COUNTS = {
    "EASTMONEY_RPT_SHAREBONUS_DET": 2620,
    "EASTMONEY_F10_PAGEAJAX_IMPLEMENTED": 93,
    "SINA_SHAREBONUS_FROZEN_HTML": 8,
    "EASTMONEY_RPT_IPO_ALLOTMENT": 7,
    "SOHU_MAJOR_EVENTS": 2,
    "THS_BONUS_HISTORY": 1,
    "EASTMONEY_F10_PAGEAJAX_FROZEN": 1,
}

FROZEN_INPUTS = {
    "ledger": {
        "workflow_run_id": 34078398130,
        "artifact_id": 10002862860,
        "artifact_name": "gp-global-qfq-missing-event-closure-v481",
        "artifact_zip_sha256": "b163727b0ded0aac2cf6e0058c5a6b05af03948c1f37b7d9525850d86af1f403",
    },
    "eastmoney_main": {
        "workflow_run_id": 34462791819,
        "artifact_id": 10146285865,
        "artifact_name": "gp12-eastmoney-sharebonus-full-pit-audit-v482",
        "artifact_zip_sha256": "9cd154e3343c6a71052fc86bf0dc5959adb8f5becf881aaa7a3c9bb60e50914d",
    },
    "f10_implemented": {
        "workflow_run_id": 34075413814,
        "artifact_id": 10001858440,
        "artifact_name": "gp-f10-missing-event-v481",
        "artifact_zip_sha256": "1c659eb28ac459d4c8ef7af9c90cbd326aaab2d95a58a47a619549d408d30d91",
    },
    "f10_frozen": {
        "workflow_run_id": 34075792988,
        "artifact_id": 10001981760,
        "artifact_name": "gp-f10-unresolved-history-v481",
        "artifact_zip_sha256": "4334772eb4397551bae45c816dc64c3cf0266775f0b13869bdc86e1705b2f0b3",
    },
    "supplemental": {
        "workflow_run_id": 34076028687,
        "artifact_id": 10002068080,
        "artifact_name": "gp-supplemental-missing-event-v481",
        "artifact_zip_sha256": "0e95dd3c49938947106abe362ea15c689cf0046e443d455afe1df32fecae756a",
    },
    "rights": {
        "workflow_run_id": 34464153949,
        "artifact_id": 10146784730,
        "artifact_name": "gp12-rights-allotment-pit-probe-v482",
        "artifact_zip_sha256": "33376facac3d87f361ae674e28532e4fefded73095edcbe67b6e6f7b9b3a06fd",
    },
}


def _day(value: object) -> str:
    text = str(value or "").strip()[:10]
    date.fromisoformat(text)
    return text


def _event_key(row: dict) -> tuple[str, str, str]:
    symbol = str(row.get("symbol") or "").strip().upper()
    source = str(row.get("source") or "").strip()
    if not symbol or not source:
        raise ValueError(f"invalid event key fields: {row}")
    return symbol, _day(row.get("ex_date")), source


def build_expected_events(ledger: dict) -> list[dict]:
    rows: list[dict] = []
    for record in ledger.get("records") or []:
        symbol = str(record.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("ledger record missing symbol")
        for event in record.get("events") or []:
            source = str(event.get("source") or "").strip()
            if not source:
                raise ValueError(f"ledger event missing source: {symbol} {event}")
            rows.append({"symbol": symbol, "ex_date": _day(event.get("ex_date")), "source": source})
    return rows


def audit_event_timing(
    expected_rows: Iterable[dict],
    observed_rows: Iterable[dict],
    required_source_counts: dict[str, int] | None = None,
) -> dict:
    expected = list(expected_rows)
    observed = list(observed_rows)

    expected_map: dict[tuple[str, str, str], dict] = {}
    for row in expected:
        key = _event_key(row)
        if key in expected_map:
            raise ValueError(f"duplicate expected event key: {key}")
        expected_map[key] = row

    observed_map: dict[tuple[str, str, str], dict] = {}
    for raw in observed:
        row = dict(raw)
        key = _event_key(row)
        if key in observed_map:
            raise ValueError(f"duplicate observed event key: {key}")
        pit_date = _day(row.get("pit_date"))
        evidence_id = str(row.get("evidence_id") or "").strip()
        if not evidence_id:
            raise ValueError(f"observed event missing evidence_id: {key}")
        row["pit_date"] = pit_date
        observed_map[key] = row

    expected_keys = set(expected_map)
    observed_keys = set(observed_map)
    missing_keys = sorted(expected_keys - observed_keys)
    extra_keys = sorted(observed_keys - expected_keys)
    covered_keys = sorted(expected_keys & observed_keys)

    late_rows = []
    for key in covered_keys:
        row = observed_map[key]
        if row["pit_date"] > key[1]:
            late_rows.append(
                {
                    "symbol": key[0],
                    "ex_date": key[1],
                    "source": key[2],
                    "pit_date": row["pit_date"],
                    "evidence_id": row["evidence_id"],
                }
            )

    source_counts = dict(sorted(Counter(k[2] for k in expected_keys).items()))
    required = dict(sorted((required_source_counts or source_counts).items()))
    source_partition_exact = source_counts == required
    status = (
        "PASS_EVENT_TIMING_ADMISSION"
        if not missing_keys and not extra_keys and not late_rows and source_partition_exact
        else "REVIEW_EVENT_TIMING_ADMISSION"
    )
    return {
        "status": status,
        "expected_n": len(expected_map),
        "covered_n": len(covered_keys),
        "missing_n": len(missing_keys),
        "extra_n": len(extra_keys),
        "late_n": len(late_rows),
        "source_counts": source_counts,
        "required_source_counts": required,
        "source_partition_exact": source_partition_exact,
        "missing_keys": [list(k) for k in missing_keys[:100]],
        "extra_keys": [list(k) for k in extra_keys[:100]],
        "late_rows": late_rows[:100],
    }


def infer_supplemental_pit_date(record: dict, ex_date: str, ledger_source: str) -> str:
    ex_date = _day(ex_date)
    context = str(record.get("context") or "")
    expected_term = str(record.get("expected_term") or "").strip()

    if ledger_source == "SINA_SHAREBONUS_FROZEN_HTML":
        row_pattern = re.compile(
            r"(\d{4}-\d{2}-\d{2})\s+"
            r"[-+]?\d+(?:\.\d+)?\s+[-+]?\d+(?:\.\d+)?\s+[-+]?\d+(?:\.\d+)?\s+"
            r"实施\s+(\d{4}-\d{2}-\d{2})"
        )
        for notice_date, candidate_ex in row_pattern.findall(context):
            if candidate_ex == ex_date:
                return _day(notice_date)

    if ledger_source in {"SOHU_MAJOR_EVENTS", "THS_BONUS_HISTORY"} and expected_term:
        pos = context.find(expected_term)
        if pos >= 0:
            prior = context[max(0, pos - 240) : pos]
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", prior)
            if dates:
                return _day(dates[-1])

    raise ValueError(
        f"cannot infer supplemental PIT date: source={ledger_source} ex_date={ex_date} "
        f"symbol={record.get('symbol')}"
    )


def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _load_csv(path: str | Path) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def collect_observed_events(
    expected_rows: list[dict],
    main_rows: list[dict],
    f10_coverage: dict,
    f10_frozen: dict,
    supplemental: dict,
    rights: dict,
) -> list[dict]:
    expected_keys = {_event_key(r) for r in expected_rows}
    observations: dict[tuple[str, str, str], dict] = {}

    def add(symbol: str, ex_date: str, source: str, pit_date: str, evidence_id: str) -> None:
        row = {
            "symbol": str(symbol).upper(),
            "ex_date": _day(ex_date),
            "source": source,
            "pit_date": _day(pit_date),
            "evidence_id": str(evidence_id),
        }
        key = _event_key(row)
        if key not in expected_keys:
            return
        if key in observations:
            raise ValueError(f"duplicate evidence for expected event key: {key}")
        observations[key] = row

    for row in main_rows:
        source = str(row.get("source") or "")
        if source != "EASTMONEY_RPT_SHAREBONUS_DET":
            continue
        matched = str(row.get("matched") or "").strip().lower()
        if matched not in {"1", "true", "yes"}:
            continue
        add(
            row.get("symbol"),
            row.get("ex_date"),
            source,
            row.get("pit_date"),
            f"EASTMONEY_FULL_PIT:{row.get('symbol')}:{row.get('ex_date')}",
        )

    f10_by_symbol = {str(r.get("symbol") or "").upper(): r for r in f10_coverage.get("records") or []}
    for symbol, ex_date, source in sorted(expected_keys):
        if source != "EASTMONEY_F10_PAGEAJAX_IMPLEMENTED":
            continue
        record = f10_by_symbol.get(symbol)
        if not record:
            continue
        for target in record.get("targets") or []:
            if _day(target.get("date")) != ex_date or target.get("status") != "F10_PAGEAJAX_TARGET_DATE_HIT":
                continue
            hits = target.get("hits") or []
            exact_hits = []
            for hit in hits:
                row = hit.get("row") or {}
                if row.get("EX_DIVIDEND_DATE") and _day(row.get("EX_DIVIDEND_DATE")) == ex_date and row.get("NOTICE_DATE"):
                    exact_hits.append(row)
            if len(exact_hits) != 1:
                raise ValueError(f"F10 implemented event requires exactly one dated hit: {(symbol, ex_date)}")
            add(symbol, ex_date, source, exact_hits[0]["NOTICE_DATE"], record.get("sha256"))

    frozen_by_key = {
        (str(r.get("symbol") or "").upper(), _day(r.get("target_date"))): r
        for r in f10_frozen.get("records") or []
        if r.get("target_date")
    }
    for symbol, ex_date, source in sorted(expected_keys):
        if source != "EASTMONEY_F10_PAGEAJAX_FROZEN":
            continue
        record = frozen_by_key.get((symbol, ex_date))
        if not record or not record.get("resolved"):
            continue
        exact_hits = []
        for hit in (record.get("pageajax") or {}).get("hits") or []:
            row = hit.get("row") or {}
            if row.get("EX_DIVIDEND_DATE") and _day(row.get("EX_DIVIDEND_DATE")) == ex_date and row.get("NOTICE_DATE"):
                exact_hits.append(row)
        if len(exact_hits) != 1:
            raise ValueError(f"F10 frozen event requires exactly one dated hit: {(symbol, ex_date)}")
        pageajax = record.get("pageajax") or {}
        evidence_id = pageajax.get("decoded_sha256") or pageajax.get("wire_sha256")
        add(symbol, ex_date, source, exact_hits[0]["NOTICE_DATE"], evidence_id)

    supplemental_by_symbol: dict[str, list[dict]] = {}
    for record in supplemental.get("records") or []:
        supplemental_by_symbol.setdefault(str(record.get("symbol") or "").upper(), []).append(record)
    supplemental_sources = {"SINA_SHAREBONUS_FROZEN_HTML", "SOHU_MAJOR_EVENTS", "THS_BONUS_HISTORY"}
    for symbol, ex_date, source in sorted(expected_keys):
        if source not in supplemental_sources:
            continue
        candidates = supplemental_by_symbol.get(symbol, [])
        source_candidates = [
            r
            for r in candidates
            if r.get("status") == "SUPPLEMENTAL_POSITIVE_EVENT_EVIDENCE"
            and (
                (source == "SINA_SHAREBONUS_FROZEN_HTML" and r.get("source") == "SINA_SHAREBONUS")
                or r.get("source") == source
            )
        ]
        if len(source_candidates) != 1:
            raise ValueError(f"supplemental source record not unique: {(symbol, ex_date, source)}")
        record = source_candidates[0]
        pit_date = infer_supplemental_pit_date(record, ex_date, source)
        add(symbol, ex_date, source, pit_date, record.get("sha256"))

    for record in rights.get("records") or []:
        if record.get("status") != "PASS":
            continue
        add(
            record.get("symbol"),
            record.get("ex_date"),
            "EASTMONEY_RPT_IPO_ALLOTMENT",
            record.get("notice_date"),
            record.get("sha256"),
        )

    return [observations[k] for k in sorted(observations)]


def _write_rows(path: Path, rows: list[dict]) -> None:
    fields = ["symbol", "ex_date", "source", "pit_date", "evidence_id", "pit_not_after_ex"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["pit_not_after_ex"] = out["pit_date"] <= out["ex_date"]
            writer.writerow({field: out.get(field) for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--main-rows", required=True)
    parser.add_argument("--main-audit", required=True)
    parser.add_argument("--f10", required=True)
    parser.add_argument("--f10-frozen", required=True)
    parser.add_argument("--supplemental", required=True)
    parser.add_argument("--rights", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    ledger = _load_json(args.ledger)
    main_audit = _load_json(args.main_audit)
    f10 = _load_json(args.f10)
    f10_frozen = _load_json(args.f10_frozen)
    supplemental = _load_json(args.supplemental)
    rights = _load_json(args.rights)

    if ledger.get("scope_n") != 847 or ledger.get("record_n") != 847 or not ledger.get("partition_exact"):
        raise ValueError("frozen V4.81 ledger checkpoint is not exact 847 scope")
    if not (
        main_audit.get("matched_n") == 2620
        and main_audit.get("missing_n") == 0
        and main_audit.get("pit_date_after_ex_n") == 0
        and main_audit.get("all_pit_dates_not_after_ex") is True
    ):
        raise ValueError("Eastmoney main PIT audit is not closed")
    if not (
        rights.get("target_event_n") == 7
        and rights.get("pass_n") == 7
        and rights.get("review_n") == 0
        and rights.get("all_notice_not_after_ex") is True
        and rights.get("all_term_linkage_match") is True
    ):
        raise ValueError("rights-allotment PIT audit is not closed")

    expected = build_expected_events(ledger)
    observed = collect_observed_events(
        expected,
        _load_csv(args.main_rows),
        f10,
        f10_frozen,
        supplemental,
        rights,
    )
    result = audit_event_timing(expected, observed, REQUIRED_SOURCE_COUNTS)
    result.update(
        {
            "artifact": "GP12_EVENT_TIMING_ADMISSION_V482",
            "version": "V4.82",
            "formal_window": ["2020-06-01", "2026-04-17"],
            "final_ledger_source": "GLOBAL_QFQ_MISSING_EVENT_CLOSURE_V481",
            "frozen_inputs": FROZEN_INPUTS,
            "promotion": {
                "event_availability_time_verified": result["status"] == "PASS_EVENT_TIMING_ADMISSION",
                "adjusted_close_blocker_closed": False,
                "turnover_ratio_blocker_closed": False,
                "label_provenance_blocker_closed": False,
                "model_freeze_allowed": False,
                "oos_metrics_allowed": False,
            },
        }
    )

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_rows(out_dir / "GP12_EVENT_TIMING_ROWS_V482.csv", observed)
    (out_dir / "GP12_EVENT_TIMING_ADMISSION_V482.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS_EVENT_TIMING_ADMISSION":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
