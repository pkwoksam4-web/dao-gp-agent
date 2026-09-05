from __future__ import annotations

import csv
import json
import os
import pathlib
import time

from run_sample50_nominal import SAMPLE50, FORMAL_BEG, FORMAL_END, THRESHOLD_BP
from sample50_official_refinements import refine_actions
from sample50_validate import (
    Action,
    compare_factor_path,
    event_ratio,
    expected_factor_for_date,
    parse_sina_qfq,
    parse_sohu_history_bytes,
    prev_close_before,
    sina_normalized_for_date,
)

OUT = pathlib.Path(os.environ.get('SAMPLE50_OUT', 'artifact_sample50'))
RAW = OUT / 'raw'


def nominal_actions(result: dict) -> list[Action]:
    out = []
    for e in result.get('events', []):
        out.append(
            Action(
                symbol=result['symbol'],
                ex_date=e['ex_date'],
                cash_per_share=float(e.get('cash_per_share_nominal') or 0.0),
                stock_ratio=float(e.get('stock_ratio') or 0.0),
                cap_ratio=float(e.get('capitalization_ratio') or 0.0),
                rights_ratio=float(e.get('rights_ratio') or 0.0),
                rights_price=e.get('rights_price'),
                source=e.get('source') or '',
            )
        )
    return out


def validate_one(symbol: str) -> dict:
    d = RAW / symbol.replace('.', '_')
    nominal_path = d / 'result.json'
    if not nominal_path.exists():
        raise FileNotFoundError(f'missing nominal result: {nominal_path}')
    nominal = json.loads(nominal_path.read_text(encoding='utf-8'))
    if nominal.get('status') == 'BLOCKED_SOURCE':
        raise RuntimeError(f'{symbol}: nominal source blocked: {nominal.get("error")}')

    raw_rows = parse_sohu_history_bytes((d / 'sohu_raw_history.js').read_bytes())
    formal_rows = [r for r in raw_rows if FORMAL_BEG <= r['date'] <= FORMAL_END]
    if not formal_rows:
        raise ValueError(f'{symbol}: no Formal rows')
    factors = parse_sina_qfq((d / 'sina_qfq.js').read_bytes())

    actions = refine_actions(symbol, nominal_actions(nominal))
    actions = [a for a in actions if FORMAL_BEG < a.ex_date <= FORMAL_END]
    ratios = {}
    for a in actions:
        p = prev_close_before(raw_rows, a.ex_date)
        ratios[a.ex_date] = event_ratio(a, p)

    expected = {
        r['date']: expected_factor_for_date(r['date'], actions, ratios, FORMAL_END)
        for r in formal_rows
    }
    actual = {
        r['date']: sina_normalized_for_date(factors, r['date'], FORMAL_END)
        for r in formal_rows
    }
    cmp = compare_factor_path(formal_rows, expected, actual, THRESHOLD_BP)
    return {
        'symbol': symbol,
        'status': 'PASS_OFFICIAL_REFINED_FACTOR' if cmp['status'] == 'PASS' else 'FAIL_OFFICIAL_REFINED_FACTOR',
        'formal_rows': len(formal_rows),
        'event_count': len(actions),
        'factor_validation': cmp,
    }


def main() -> None:
    results = []
    for symbol in SAMPLE50:
        result = validate_one(symbol)
        results.append(result)
        print(
            json.dumps(
                {
                    'progress': len(results),
                    'symbol': symbol,
                    'status': result['status'],
                    'max_diff_bp': result['factor_validation']['max_diff_bp'],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    passed = sum(r['status'] == 'PASS_OFFICIAL_REFINED_FACTOR' for r in results)
    max_result = max(results, key=lambda r: r['factor_validation']['max_diff_bp'])
    summary = {
        'artifact': 'GP_SAMPLE50_OFFICIAL_REFINED_FACTOR_CROSSCHECK_V479',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'sample_version': 'V3.67_FROZEN',
        'sample_n': len(SAMPLE50),
        'formal_window': [FORMAL_BEG, FORMAL_END],
        'threshold_bp': THRESHOLD_BP,
        'passed': passed,
        'failed': len(SAMPLE50) - passed,
        'all_pass': passed == len(SAMPLE50),
        'max_diff_bp': max_result['factor_validation']['max_diff_bp'],
        'max_diff_symbol': max_result['symbol'],
        'formal_oos_allowed': False,
        'interpretation': (
            'Official implementation-announcement virtual/effective distributions are '
            'applied only where nominal event terms are not the exchange ex-right basis. '
            'This closes the Sample50 adjustment-provenance gate only; PIT-ST/global-847 '
            'gates remain separate.'
        ),
        'results': results,
    }
    (OUT / 'sample50_exact_results_v479.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    with (OUT / 'sample50_exact_summary_v479.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['order', 'symbol', 'status', 'formal_rows', 'event_count', 'max_diff_bp'])
        for i, r in enumerate(results, 1):
            w.writerow(
                [
                    i,
                    r['symbol'],
                    r['status'],
                    r['formal_rows'],
                    r['event_count'],
                    r['factor_validation']['max_diff_bp'],
                ]
            )

    print(
        json.dumps(
            {
                'done': True,
                'passed': passed,
                'failed': len(SAMPLE50) - passed,
                'max_diff_symbol': summary['max_diff_symbol'],
                'max_diff_bp': summary['max_diff_bp'],
            },
            ensure_ascii=False,
        )
    )
    if not summary['all_pass']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
