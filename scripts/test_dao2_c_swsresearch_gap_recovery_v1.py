import json

from dao2_c_swsresearch_gap_recovery_v1 import (
    extract_gap_rows,
    normalize_trend_rows,
    compare_recovered_to_ledger_candidates,
)


def test_extract_gap_rows_uses_schema_not_positions():
    ledger = {
        "row_schema": [
            "sector_code", "trade_date", "gap_class", "candidate_close_2dp", "admitted"
        ],
        "rows": [
            ["801010.SI", "20210806", "DERIVED_CLOSE_EVIDENCE_ONLY", 3185.66, False],
            ["801020.SI", "20210806", "DIRECT_RAW_REQUIRED", None, False],
        ],
    }
    rows = extract_gap_rows(ledger)
    assert rows == [
        {
            "sector_code": "801010.SI",
            "trade_date": "20210806",
            "gap_class": "DERIVED_CLOSE_EVIDENCE_ONLY",
            "candidate_close_2dp": 3185.66,
            "admitted": False,
        },
        {
            "sector_code": "801020.SI",
            "trade_date": "20210806",
            "gap_class": "DIRECT_RAW_REQUIRED",
            "candidate_close_2dp": None,
            "admitted": False,
        },
    ]


def test_extract_gap_rows_normalizes_iso_trade_dates_to_compact_keys():
    ledger = {
        "row_schema": ["sector_code", "trade_date", "candidate_close_2dp"],
        "rows": [["801010.SI", "2021-08-06", 3185.66]],
    }
    rows = extract_gap_rows(ledger)
    assert rows[0]["trade_date"] == "20210806"


def test_normalize_trend_rows_keeps_direct_ohlc_and_code_identity():
    payload = {
        "data": [
            {
                "swindexcode": "801010",
                "bargaindate": "2021-08-06",
                "openindex": "3100.10",
                "maxindex": "3200.20",
                "minindex": "3090.30",
                "closeindex": "3185.66",
                "bargainamount": "123",
                "bargainsum": "456",
            }
        ]
    }
    rows = normalize_trend_rows(json.dumps(payload).encode(), expected_code="801010")
    assert rows == [
        {
            "sector_code": "801010.SI",
            "trade_date": "20210806",
            "open": 3100.10,
            "high": 3200.20,
            "low": 3090.30,
            "close": 3185.66,
            "volume": 123.0,
            "amount": 456.0,
        }
    ]


def test_candidate_comparison_is_exact_at_frozen_2dp_only_for_rows_with_candidate():
    gaps = [
        {"sector_code": "801010.SI", "trade_date": "20210806", "candidate_close_2dp": 3185.66},
        {"sector_code": "801020.SI", "trade_date": "20210806", "candidate_close_2dp": None},
    ]
    recovered = [
        {"sector_code": "801010.SI", "trade_date": "20210806", "close": 3185.66},
        {"sector_code": "801020.SI", "trade_date": "20210806", "close": 3037.56},
    ]
    result = compare_recovered_to_ledger_candidates(gaps, recovered)
    assert result["candidate_rows"] == 1
    assert result["matched_2dp"] == 1
    assert result["mismatched_2dp"] == 0
