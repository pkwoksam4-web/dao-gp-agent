import json
from pathlib import Path

import pytest

from scripts.dao2_a_ifind_exact_probe_v2 import (
    FROZEN_CONTROL_PATH,
    LEDGER_PATH,
    candidate_mappings,
    load_frozen_controls,
    load_residual_keys,
    score_candidate,
)


def test_frozen_controls_are_exactly_8_rows_and_32_comparisons():
    controls = load_frozen_controls(Path(FROZEN_CONTROL_PATH))
    assert len(controls) == 8
    assert len(controls) * 4 == 32


def test_candidate_set_is_predefined_and_global_only():
    candidates = candidate_mappings()
    assert candidates
    assert {c['scale'] for c in candidates} <= {1, 0.0001, 10000}
    for c in candidates:
        assert set(c['mapping']) == {
            'buy_lg_amount', 'buy_elg_amount', 'sell_lg_amount', 'sell_elg_amount'
        }


def test_global_candidate_requires_32_of_32_exact():
    controls = [
        {
            'normalized_row': {
                'ts_code': f'{i:06d}.SZ',
                'trade_date': '2023-05-22',
                'buy_lg_amount': '1.00',
                'buy_elg_amount': '2.00',
                'sell_lg_amount': '3.00',
                'sell_elg_amount': '4.00',
            }
        }
        for i in range(8)
    ]
    rows = {
        (c['normalized_row']['ts_code'], c['normalized_row']['trade_date']): {
            'activeBuyMainAmt': 1.00,
            'activeBuyLargeAmt': 2.00,
            'activeSellMainAmt': 3.00,
            'activeSellLargeAmt': 4.00,
        }
        for c in controls
    }
    mapping = {
        'buy_lg_amount': 'activeBuyMainAmt',
        'buy_elg_amount': 'activeBuyLargeAmt',
        'sell_lg_amount': 'activeSellMainAmt',
        'sell_elg_amount': 'activeSellLargeAmt',
    }
    result = score_candidate(controls, rows, mapping, 1)
    assert result['exact_comparisons'] == 32
    assert result['mismatch_count'] == 0
    assert result['pass'] is True

    first_key = next(iter(rows))
    rows[first_key]['activeSellLargeAmt'] = 4.01
    failed = score_candidate(controls, rows, mapping, 1)
    assert failed['exact_comparisons'] == 31
    assert failed['mismatch_count'] == 1
    assert failed['pass'] is False


def test_residual_keys_are_loaded_only_from_authoritative_ledger():
    keys = load_residual_keys(Path(LEDGER_PATH))
    assert len(keys) == 16
    assert ('002118.SZ', '2023-05-22') in keys
    assert ('002503.SZ', '2023-05-22') in keys
    assert ('002504.SZ', '2023-05-22') in keys
    assert ('002118.SZ', '2023-03-20') not in keys
