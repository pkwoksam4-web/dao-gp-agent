from __future__ import annotations
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ARCHIVE_SHA = "d526b1341694e14b13ee753200165c0701c3948f984a2e96211bb812f856f03d"
RUN_BACKTEST_SHA = "6b81feaa37ade4970fcda62601e2a699951fe00ef678ee83fa84f84928d69ff1"
RUN_PANEL_SHA = "62229450e488a75ba4352a239fc762a2b9f48034f765966242632970937278c2"
FORMAL_PIPE_SHA = "dde897aa7daeca318ab438cd985d7708a5db7b7bc89a7cb47ef231a4aad94c8c"
TARGETS = ["up_close_1","up_close_2","up_close_3","hit_up2_3d","hit_up4_3d","hit_dn2_3d"]
CORRECTIONS = {
    ("002087.SZ","2024-06-13"),
    ("600647.SH","2024-06-13"),
    ("600766.SH","2024-06-13"),
    ("603133.SH","2024-06-13"),
}

def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def derive_status(*, is_st_raw: str, tradestatus_raw: str,
                  close: str | float | None, up_limit: str | float | None) -> dict:
    if is_st_raw not in {"0","1"} or tradestatus_raw not in {"0","1"}:
        raise ValueError("unknown PIT-ST state")
    is_st = is_st_raw == "1"
    tradable = tradestatus_raw == "1"
    if not tradable:
        upper_limit = False
    else:
        if close is None or up_limit is None:
            raise ValueError("tradable row requires close and up_limit")
        try:
            c, u = Decimal(str(close)), Decimal(str(up_limit))
        except InvalidOperation as exc:
            raise ValueError("invalid price-limit input") from exc
        if not c.is_finite() or not u.is_finite():
            raise ValueError("invalid price-limit input")
        upper_limit = c == u
    return {
        "is_st": is_st,
        "tradable": tradable,
        "upper_limit": upper_limit,
        "status_entry_eligible": (not is_st) and tradable and (not upper_limit),
    }

def validate() -> dict:
    d = load_json("data/dao2/modules/D_LABEL_STATUS_DISCOVERY_V1.json")
    b = load_json("data/GP12_LABEL_STATUS_BINDING_V1.json")
    s = load_json("data/dao2/modules/D_LABEL_STATUS_STATE_V1.json")

    pit = d["formal_pit_st"]
    assert pit["status"] == "FORMAL_BASE_COMPLETE"
    assert pit["lifecycle_pass"] == "847/847"
    assert pit["calendar_pass"] == "1426/1426"
    assert pit["missing_required_dates_total"] == 0
    assert pit["duplicate_daily_keys"] == 0
    assert pit["invalid_daily_rows"] == 0
    assert pit["outside_calendar_rows"] == 0
    assert pit["transition_crosscheck"] == "6/6 PASS"
    assert pit["formal_overlay_rows"] == 1021953

    supplement = d["course_stock_st_supplement"]
    assert supplement["formal_missing_date_count"] == 12
    assert supplement["role"] == "SUPPLEMENTARY_CROSSCHECK_ONLY"
    assert supplement["blocks_formal_pit_st"] is False

    corr = d["v482_tradestatus_corrections"]
    assert corr["correction_count"] == 4
    assert {tuple(x) for x in corr["exact_point_corrections"]} == CORRECTIONS
    assert corr["isST_changed"] is False

    lim = d["course_price_limit_source"]
    assert lim["provider"] == "Tushare"
    assert lim["endpoint"] == "stk_limit(trade_date=date)"
    assert lim["open_dates_20160104_20260518"] == lim["limit_date_files"] == 2516
    assert lim["formal_open_dates_20200601_20260417"] == 1426
    assert lim["downloader_blob_sha"] == "f00fed00a969a39a73a71152fb3031e1631c3476"

    hp = b["historical_label_provenance"]
    assert hp["status"] == "BOUND_FILE_BACKED"
    assert hp["source_archive"]["sha256"] == ARCHIVE_SHA
    file_hashes = {x["path"]:x["sha256"] for x in hp["source_files"]}
    assert file_hashes["src/run_backtest.py"] == RUN_BACKTEST_SHA
    assert file_hashes["src/run_panel_backtest.py"] == RUN_PANEL_SHA
    assert file_hashes["src/run_formal_pipeline.py"] == FORMAL_PIPE_SHA
    assert hp["probability_targets"] == TARGETS
    assert hp["target_horizons_market_days"] == {
        "up_close_1":1,"up_close_2":2,"up_close_3":3,
        "hit_up2_3d":3,"hit_up4_3d":3,"hit_dn2_3d":3,
    }
    assert hp["target_specific_purge"] is True
    assert "market trading calendar" in hp["label_clock"]
    assert "not fill-price mechanics" in hp["execution_diagnostics_boundary"]

    sc = b["status_contract"]
    assert sc["required_fields"] == ["known_at","is_st","tradable","upper_limit"]
    assert sc["strict_boolean_fields"] == ["is_st","tradable","upper_limit"]
    assert sc["final_status_eligibility"]["formula"] == "status_entry_eligible = (not is_st) and tradable and (not upper_limit)"
    assert sc["upper_limit"]["missing_tradable_input_policy"].endswith("fail closed.")
    assert "never shifted" in sc["future_horizon_rule"]["target_dates"]
    assert "do not define actual fill prices" in sc["future_horizon_rule"]["fills"]

    gov = b["governance"]
    assert gov["candidate_label_is_historical_label"] is False
    assert gov["course_repo_label_code_substituted_for_historical"] is False
    assert gov["future_leakage_allowed"] is False
    assert gov["execution_diagnostics_are_fill_mechanics"] is False
    assert gov["forward_fill"] is False
    assert gov["silent_proxy_substitution"] is False
    assert gov["model_freeze_allowed"] is False
    assert gov["oos_metrics_allowed"] is False

    assert s["module_id"] == "D"
    assert s["status"] in {"VERIFYING","PASS","FROZEN"}
    assert s["progress"]["historical_label_provenance_bound"] is True
    assert s["progress"]["status_semantics_complete"] is True
    return {"valid":True,"module_id":"D","label_provenance":"BOUND","status_semantics":"COMPLETE"}

if __name__ == "__main__":
    print(json.dumps(validate(), ensure_ascii=False, indent=2))
