import json

from dao2_c_swsresearch_trend_probe_v1 import (
    TARGET_DATES,
    NEIGHBOR_DATES,
    normalize_trend_rows,
    normalize_analysis_rows,
    validate_neighbor_overlap,
)


def test_normalize_trend_rows_extracts_official_ohlc():
    payload = {
        "data": [
            {
                "swindexcode": "801020",
                "bargaindate": "2021-08-06",
                "openindex": "3210.11",
                "maxindex": "3250.22",
                "minindex": "3190.33",
                "closeindex": "3240.44",
                "bargainamount": "123",
                "bargainsum": "456",
            }
        ]
    }
    rows = normalize_trend_rows(json.dumps(payload).encode())
    assert rows == [
        {
            "industry_code": "801020.SI",
            "trade_date": "20210806",
            "open": 3210.11,
            "high": 3250.22,
            "low": 3190.33,
            "close": 3240.44,
            "volume": 123.0,
            "amount": 456.0,
        }
    ]


def test_normalize_analysis_rows_extracts_direct_same_day_close():
    payload = {
        "data": {
            "count": 1,
            "results": [
                {
                    "swindexcode": "801020",
                    "bargaindate": "2021-08-06",
                    "closeindex": "3240.44",
                    "bargainamount": "123",
                    "markup": "1.25",
                }
            ],
        }
    }
    rows = normalize_analysis_rows(json.dumps(payload).encode())
    assert rows == [
        {
            "industry_code": "801020.SI",
            "trade_date": "20210806",
            "close": 3240.44,
            "volume": 123.0,
            "markup": 1.25,
        }
    ]


def test_target_and_neighbor_contract_is_frozen():
    assert TARGET_DATES == ["20210806", "20211008", "20211022"]
    assert NEIGHBOR_DATES == [
        "20210805", "20210809", "20210930", "20211011", "20211021", "20211025"
    ]


def test_neighbor_overlap_requires_exact_close_match():
    source = [
        {"industry_code": "801020.SI", "trade_date": d, "close": 100.0 + i}
        for i, d in enumerate(NEIGHBOR_DATES)
    ]
    base = {(r["industry_code"], r["trade_date"]): r["close"] for r in source}
    result = validate_neighbor_overlap(source, base)
    assert result["status"] == "PASS_EXACT_NEIGHBOR_OVERLAP"
    assert result["matched"] == 6

    base[("801020.SI", NEIGHBOR_DATES[-1])] += 0.01
    result = validate_neighbor_overlap(source, base)
    assert result["status"] == "FAIL_NEIGHBOR_OVERLAP"
    assert result["matched"] == 5
