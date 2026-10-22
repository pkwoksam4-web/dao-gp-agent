from pathlib import Path


def test_workflow_uses_frozen_controls_and_authoritative_ledger():
    text = Path('.github/workflows/dao2-a-ifind-exact-probe-v1.yml').read_text(encoding='utf-8')
    assert 'A_JESSICA_KNOWN_ROW_CONTROL_SCOPE_V1.json' in text
    assert 'GP12_CANDIDATE_MAIN_NET_FLOW_RESIDUAL_LEDGER_V1.json' in text
    assert '3 Jessica rows per target date' not in text
    assert '32/32' in text or '32' in text
    assert 'activeBuyMainAmt' in text
    assert 'activeBuyLargeAmt' in text
    assert 'activeSellMainAmt' in text
    assert 'activeSellLargeAmt' in text
