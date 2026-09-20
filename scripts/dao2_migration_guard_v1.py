from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "data" / "DAO2_MIGRATION_STATE_V1.json"

EXPECTED_BLOCKERS = {
    "LABEL_PROVENANCE_UNBOUND",
    "MAIN_NET_FLOW_UNBOUND",
    "MARKET_BENCHMARK_UNBOUND",
    "MARKET_BREADTH_UNBOUND",
    "SECTOR_BREADTH_UNBOUND",
    "SECTOR_MEMBERSHIP_PIT_UNBOUND",
    "SECTOR_SERIES_UNBOUND",
    "STATUS_SEMANTICS_INCOMPLETE",
    "TURNOVER_RATIO_UNBOUND",
}
EXPECTED_READY = {"F6","F7","F8","F9","F10","F12"}
EXPECTED_BLOCKED = {"F1","F2","F3","F4","F5","F11"}


def validate_state(state: dict) -> dict:
    assert state["artifact"] == "DAO2_MIGRATION_STATE_V1"
    assert state["quant_version"] == "V4.82"
    formal = state["formal"]
    assert formal["calendar_days"] == 1426
    assert formal["universe_n"] == 847
    assert formal["formal_symbol_n"] == 844
    assert formal["raw_trade_rows"] == 1011607
    assert formal["liquidity_threshold_cny"] == 80000000
    assert formal["formal_ready"] is True
    assert formal["model_freeze_allowed"] is False
    assert formal["oos_metrics_allowed"] is False

    gp12 = state["gp12"]
    assert gp12["strategy_id"] == "GP12_REBUILD_CANDIDATE_V1"
    assert gp12["historical_gp_v11_recovered"] is False
    assert gp12["candidate_adoption_status"] == "UNAPPROVED"
    assert set(gp12["ready_factors"]) == EXPECTED_READY
    assert set(gp12["blocked_factors"]) == EXPECTED_BLOCKED
    assert set(gp12["blockers"]) == EXPECTED_BLOCKERS

    gov = state["governance"]
    assert gov["fail_closed"] is True
    assert gov["forward_fill"] is False
    assert gov["silent_proxy_substitution"] is False
    assert gov["ci_equals_model_success"] is False
    assert gov["reverse_check_required"] is True

    return {
        "migration_state_valid": True,
        "blocker_count": len(gp12["blockers"]),
        "model_freeze_allowed": formal["model_freeze_allowed"],
        "oos_metrics_allowed": formal["oos_metrics_allowed"],
    }


def main() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    print(json.dumps(validate_state(state), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
