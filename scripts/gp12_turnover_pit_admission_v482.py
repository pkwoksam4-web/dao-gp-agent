from __future__ import annotations

import math
from typing import Iterable


FIELDS = ("turn", "volume", "amount", "tradestatus", "isST")
TOL = {"turn": 5e-7, "volume": 0.0, "amount": 5e-5, "tradestatus": 0.0, "isST": 0.0}
UNIVERSE_SYMBOL_N = 847
ROW_BEARING_SYMBOL_N = 844
NOT_APPLICABLE_SYMBOL_N = 3


def _key(row: dict) -> tuple[str, str]:
    symbol = str(row.get("symbol") or "").strip().upper()
    day = str(row.get("date") or "").strip()[:10]
    if not symbol or len(day) != 10:
        raise ValueError(f"invalid turnover row key: {row}")
    return symbol, day


def _num(value):
    if value is None or value == "":
        return None
    x = float(value)
    return x if math.isfinite(x) else None


def _rows_map(rows: Iterable[dict], label: str) -> dict[tuple[str, str], dict]:
    out = {}
    for raw in rows:
        row = dict(raw)
        k = _key(row)
        if k in out:
            raise ValueError(f"duplicate {label} turnover key: {k}")
        out[k] = row
    return out


def _field_diffs(a: dict, b: dict, fields=FIELDS) -> list[str]:
    bad = []
    for field in fields:
        av, bv = _num(a.get(field)), _num(b.get(field))
        if av is None or bv is None:
            if av != bv:
                bad.append(field)
            continue
        if abs(av - bv) > TOL[field]:
            bad.append(field)
    return bad


def audit_replay(baseline_rows: Iterable[dict], replay_rows: Iterable[dict]) -> dict:
    base = _rows_map(baseline_rows, "baseline")
    replay = _rows_map(replay_rows, "replay")
    bk, rk = set(base), set(replay)
    common = sorted(bk & rk)
    mismatches = []
    for k in common:
        fields = _field_diffs(base[k], replay[k])
        if fields:
            mismatches.append({
                "symbol": k[0],
                "date": k[1],
                "fields": fields,
                "baseline": {f: base[k].get(f) for f in fields},
                "replay": {f: replay[k].get(f) for f in fields},
            })
    missing = sorted(bk-rk)
    extra = sorted(rk-bk)
    status = "PASS_REPLAY_EXACT" if not missing and not extra and not mismatches else "REVIEW_REPLAY_EXACT"
    return {
        "status": status,
        "expected_n": len(base),
        "matched_n": len(common)-len(mismatches),
        "missing_n": len(missing),
        "extra_n": len(extra),
        "mismatch_n": len(mismatches),
        "missing": [list(x) for x in missing[:100]],
        "extra": [list(x) for x in extra[:100]],
        "mismatches": mismatches[:100],
    }


def audit_prefix_invariance(full_rows: Iterable[dict], prefix_rows: Iterable[dict], cutoff: str) -> dict:
    expected = [dict(r) for r in full_rows if _key(r)[1] <= cutoff]
    x = audit_replay(expected, prefix_rows)
    return {
        **x,
        "status": "PASS_PREFIX_INVARIANCE" if x["status"] == "PASS_REPLAY_EXACT" else "REVIEW_PREFIX_INVARIANCE",
        "cutoff": cutoff,
    }


def audit_adjustflag_invariance(rows_by_flag: dict[str, Iterable[dict]]) -> dict:
    flags = sorted(rows_by_flag)
    if "3" not in flags:
        raise ValueError("adjustflag=3 baseline is required")
    base = list(rows_by_flag["3"])
    total_mismatch = total_missing = total_extra = 0
    details = []
    symbols = {_key(r)[0] for r in base}
    for flag in flags:
        if flag == "3":
            continue
        x = audit_replay(base, rows_by_flag[flag])
        total_mismatch += x["mismatch_n"]
        total_missing += x["missing_n"]
        total_extra += x["extra_n"]
        details.append({"flag": flag, **x})
    status = (
        "PASS_ADJUSTFLAG_INVARIANCE"
        if total_mismatch == total_missing == total_extra == 0
        else "REVIEW_ADJUSTFLAG_INVARIANCE"
    )
    return {
        "status": status,
        "symbol_n": len(symbols),
        "flags": flags,
        "mismatch_n": total_mismatch,
        "missing_n": total_missing,
        "extra_n": total_extra,
        "details": details,
    }


def select_turnover_probe_symbols(symbols: Iterable[str], sample_n: int = 50) -> list[str]:
    universe = sorted({str(s).strip().upper() for s in symbols if str(s).strip()})
    if sample_n <= 0 or sample_n > len(universe):
        raise ValueError(f"probe sample size {sample_n} is invalid for universe size {len(universe)}")
    return universe[:sample_n]


def build_turnover_pit_admission(structural: dict, replay: dict, prefix: dict, adjustflag: dict) -> dict:
    structural_ok = (
        structural.get("status") == "PASS_STRUCTURAL_PITST_ALIGNED_TURNOVER"
        and structural.get("aligned_trade_rows") == 1011607
        and structural.get("sohu_trade_rows") == 1011607
        and structural.get("exact_symbol_date_coverage") is True
        and structural.get("turn_missing_n") == 0
        and structural.get("turn_negative_n") == 0
    )
    if not structural_ok:
        raise ValueError("structural turnover coverage is not closed")

    replay_ok = (
        replay.get("status") == "PASS_REPLAY_EXACT"
        and replay.get("expected_n") == 1011607
        and replay.get("matched_n") == 1011607
        and replay.get("missing_n") == 0
        and replay.get("extra_n") == 0
        and replay.get("mismatch_n") == 0
    )
    if not replay_ok:
        raise ValueError("historical replay is not exact")

    prefix_ok = (
        prefix.get("status") == "PASS_PREFIX_MATRIX_INVARIANCE"
        and prefix.get("symbol_n") == ROW_BEARING_SYMBOL_N
        and prefix.get("probe_n") == ROW_BEARING_SYMBOL_N
        and prefix.get("missing_n") == 0
        and prefix.get("extra_n") == 0
        and prefix.get("mismatch_n") == 0
        and prefix.get("query_error_n", 0) == 0
    )
    if not prefix_ok:
        raise ValueError("historical prefix invariance is not closed")

    flag_ok = (
        adjustflag.get("status") == "PASS_ADJUSTFLAG_INVARIANCE"
        and adjustflag.get("symbol_n") == 50
        and adjustflag.get("missing_n") == 0
        and adjustflag.get("extra_n") == 0
        and adjustflag.get("mismatch_n") == 0
        and adjustflag.get("query_error_n", 0) == 0
    )
    if not flag_ok:
        raise ValueError("adjustflag invariance is not closed")

    return {
        "artifact": "GP12_TURNOVER_RATIO_PIT_ADMISSION_V482",
        "version": "V4.82",
        "status": "PASS_TURNOVER_RATIO_PIT_ADMISSION",
        "formal_window": ["2020-06-01", "2026-04-17"],
        "scope": {
            "universe_symbol_n": UNIVERSE_SYMBOL_N,
            "row_bearing_symbol_n": ROW_BEARING_SYMBOL_N,
            "not_applicable_symbol_n": NOT_APPLICABLE_SYMBOL_N,
            "trade_row_n": 1011607,
            "sample_adjustflag_symbol_n": 50,
        },
        "pit_contract": {
            "source_native_daily_field": "BaoStock query_history_k_data_plus.turn",
            "source_unit": "percent",
            "production_transform": "turn / 100.0",
            "future_price_adjustment_dependency_rejected": True,
            "historical_replay_exact_required": True,
            "query_horizon_invariance_required": True,
            "adjustflag_invariance_required": True,
            "scope_partition_required": "847 universe = 844 row-bearing + 3 NOT_APPLICABLE",
        },
        "promotion": {
            "turnover_ratio_pit_verified": True,
            "turnover_ratio_blocker_closed": True,
            "label_provenance_blocker_closed": False,
            "formal_feature_ready": False,
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
        },
        "remaining_gp12_blockers": ["LABEL_PROVENANCE_UNBOUND"],
    }
