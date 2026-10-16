from __future__ import annotations

import hashlib
from typing import Iterable

from simple_baseline_v1 import compute_latest_baseline

BASELINE_VERSION = "MOMENTUM_VOL_REGIME_V1"


def _validate_inputs(session_ids: list[str], closes: list[float]) -> None:
    if len(session_ids) != len(closes):
        raise ValueError("LENGTH_MISMATCH")
    if not session_ids:
        raise ValueError("EMPTY_INPUT")
    for i in range(1, len(session_ids)):
        if session_ids[i] <= session_ids[i - 1]:
            raise ValueError("SESSION_IDS_NOT_STRICTLY_INCREASING")


def _input_hash(session_ids: list[str], closes: list[float]) -> str:
    h = hashlib.sha256()
    for sid, close in zip(session_ids, closes):
        h.update(f"{sid}\t{float(close):.17g}\n".encode("utf-8"))
    return h.hexdigest()


def build_baseline_series(
    session_ids: Iterable[str],
    closes: Iterable[float],
) -> tuple[list[dict], dict]:
    sessions = [str(x) for x in session_ids]
    xs = [float(x) for x in closes]
    _validate_inputs(sessions, xs)

    rows: list[dict] = []
    for i, sid in enumerate(sessions):
        result = compute_latest_baseline(xs[: i + 1])
        rows.append({
            "session_id": sid,
            "baseline_version": BASELINE_VERSION,
            **result,
        })

    meta = {
        "baseline_version": BASELINE_VERSION,
        "row_count": len(rows),
        "first_session_id": sessions[0],
        "last_session_id": sessions[-1],
        "input_sha256": _input_hash(sessions, xs),
        "data_cutoff_policy": "COMPLETED_SESSION_ONLY",
    }
    return rows, meta
