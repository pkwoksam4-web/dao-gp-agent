from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Iterable

SW2014_LAST = "20211210"
SW2021_FIRST = "20211213"


def _date(value: object) -> str:
    text = str(value or "").replace("-", "").strip()
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"invalid date: {value!r}")
    return text


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _formal_dates(rows: Iterable[dict[str, str]]) -> list[str]:
    out: list[str] = []
    for row in rows:
        if "is_open" in row and str(row["is_open"]).strip() not in {"1", "1.0", "true", "True"}:
            continue
        raw = row.get("trade_date") or row.get("cal_date") or row.get("date")
        if not raw:
            raise ValueError("formal calendar requires trade_date, cal_date, or date")
        out.append(_date(raw))
    dates = sorted(set(out))
    if dates != out:
        raise ValueError("formal calendar must be unique and strictly increasing")
    return dates


def interval_active(row: dict[str, str], trade_date: str) -> bool:
    start = _date(row["in_date"])
    raw_end = str(row.get("out_date") or "").strip()
    end = _date(raw_end) if raw_end and raw_end.lower() not in {"nan", "none", "null"} else None
    return start <= trade_date and (end is None or trade_date <= end)


def validate_membership(
    rows: list[dict[str, str]],
    unresolved_rows: list[dict[str, str]],
) -> dict:
    errors: list[str] = []
    required = {"ts_code", "industry_code", "in_date", "out_date", "taxonomy_version", "mapping_method"}
    seen: set[tuple[str, ...]] = set()

    if not rows:
        errors.append("membership_empty")

    for index, row in enumerate(rows, start=1):
        missing = sorted(k for k in required if k not in row)
        if missing:
            errors.append(f"row_{index}:missing_columns:{','.join(missing)}")
            continue
        try:
            start = _date(row["in_date"])
            raw_end = str(row.get("out_date") or "").strip()
            end = _date(raw_end) if raw_end and raw_end.lower() not in {"nan", "none", "null"} else None
        except ValueError as exc:
            errors.append(f"row_{index}:{exc}")
            continue

        if end is not None and start > end:
            errors.append(f"row_{index}:interval_reversed")

        taxonomy = row["taxonomy_version"]
        method = row["mapping_method"]
        if taxonomy == "SW2014_projected":
            if start > SW2014_LAST:
                errors.append(f"row_{index}:sw2014_projected_starts_after_switch")
            if end is None or end > SW2014_LAST:
                errors.append(f"row_{index}:sw2014_projected_extends_after_20211210")
            if method == "native_sw2021":
                errors.append(f"row_{index}:projected_row_marked_native")
        elif taxonomy == "SW2021":
            if start < SW2021_FIRST:
                errors.append(f"row_{index}:sw2021_starts_before_20211213")
            if method != "native_sw2021":
                errors.append(f"row_{index}:sw2021_not_marked_native")
        else:
            errors.append(f"row_{index}:unknown_taxonomy:{taxonomy}")

        key = (
            row["ts_code"],
            row["industry_code"],
            start,
            end or "",
            taxonomy,
        )
        if key in seen:
            errors.append(f"row_{index}:duplicate_interval")
        seen.add(key)

    if unresolved_rows:
        errors.append(f"unresolved_membership_rows_present:{len(unresolved_rows)}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "rows": len(rows),
        "unresolved_rows": len(unresolved_rows),
        "taxonomy_switch_valid": not any(
            "sw2014_" in err or "sw2021_" in err or "unknown_taxonomy" in err for err in errors
        ),
        "pit_valid": not errors,
        "errors": errors,
    }


def required_sector_keys(
    membership_rows: list[dict[str, str]],
    formal_dates: list[str],
) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for date in formal_dates:
        for row in membership_rows:
            if interval_active(row, date):
                code = str(row.get("industry_code") or "").strip()
                if code:
                    keys.add((code, date))
    return keys


def validate_series(
    rows: list[dict[str, str]],
    expected_keys: set[tuple[str, str]],
) -> dict:
    errors: list[str] = []
    observed: set[tuple[str, str]] = set()
    required = {
        "industry_code",
        "trade_date",
        "close",
        "source_provider",
        "source_trade_date",
        "fill_method",
    }

    if not expected_keys:
        errors.append("expected_sector_keys_empty")

    for index, row in enumerate(rows, start=1):
        missing = sorted(k for k in required if k not in row)
        if missing:
            errors.append(f"row_{index}:missing_columns:{','.join(missing)}")
            continue
        try:
            trade_date = _date(row["trade_date"])
            source_trade_date = _date(row["source_trade_date"])
            close = float(row["close"])
        except (ValueError, TypeError) as exc:
            errors.append(f"row_{index}:invalid_value:{exc}")
            continue

        key = (str(row["industry_code"]).strip(), trade_date)
        if key in observed:
            errors.append(f"row_{index}:duplicate_sector_date")
        observed.add(key)

        if source_trade_date != trade_date:
            errors.append(f"row_{index}:source_trade_date_mismatch")
        if str(row["fill_method"]).strip().upper() != "NONE":
            errors.append(f"row_{index}:fill_method_not_none")
        if not math.isfinite(close) or close <= 0:
            errors.append(f"row_{index}:invalid_close")
        if not str(row["source_provider"]).strip():
            errors.append(f"row_{index}:missing_source_provider")

        provenance_type = str(row.get("provenance_type") or "").strip().upper()
        if provenance_type == "DERIVED_CLOSE":
            errors.append(f"row_{index}:derived_close_not_admitted")
        elif provenance_type and provenance_type != "RAW_CLOSE":
            errors.append(f"row_{index}:unknown_provenance_type:{provenance_type}")

    missing_keys = sorted(expected_keys - observed)
    if missing_keys:
        errors.append(f"missing_required_sector_dates:{len(missing_keys)}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "rows": len(rows),
        "required_keys": len(expected_keys),
        "observed_keys": len(observed),
        "missing_required_keys": len(missing_keys),
        "missing_required_key_sample": [
            {"industry_code": code, "trade_date": date}
            for code, date in missing_keys[:20]
        ],
        "no_forward_fill_proven": not any("fill_method" in err or "source_trade_date" in err for err in errors),
        "derived_close_admitted": False,
        "derived_close_rows_rejected": sum("derived_close_not_admitted" in err for err in errors),
        "full_coverage": not missing_keys,
        "errors": errors,
    }


def verify_candidate_package(
    formal_rows: list[dict[str, str]],
    membership_rows: list[dict[str, str]],
    unresolved_rows: list[dict[str, str]],
    series_rows: list[dict[str, str]],
) -> dict:
    dates = _formal_dates(formal_rows)
    membership = validate_membership(membership_rows, unresolved_rows)
    expected = required_sector_keys(membership_rows, dates)
    series = validate_series(series_rows, expected)
    passed = membership["status"] == "PASS" and series["status"] == "PASS"
    return {
        "artifact": "DAO2_C_SECTOR_PIT_CANDIDATE_VALIDATION_V1",
        "status": "PASS_CANDIDATE_INPUTS" if passed else "BLOCKED",
        "formal_calendar": {
            "start": dates[0] if dates else None,
            "end": dates[-1] if dates else None,
            "observed_n": len(dates),
        },
        "membership": membership,
        "series": series,
        "sector_breadth_derivation_allowed": passed,
        "historical_gp_v11_recovery_claim_allowed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail-closed DAO2 Module C sector PIT verifier.")
    parser.add_argument("--formal-calendar", type=Path, required=True)
    parser.add_argument("--membership", type=Path, required=True)
    parser.add_argument("--unresolved-membership", type=Path, required=True)
    parser.add_argument("--series", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = verify_candidate_package(
        _read_csv(args.formal_calendar),
        _read_csv(args.membership),
        _read_csv(args.unresolved_membership),
        _read_csv(args.series),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS_CANDIDATE_INPUTS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
