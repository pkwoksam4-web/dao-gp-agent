from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.btc_shadow2_archive_capture import archive_capture as binance_base
from runtime.btc_successor_b_okx_gap_capture import okx_gap_capture as okx_base

EXPERIMENT_ID = 'BTC-FLOW-SUCCESSOR-20261009-B'
RELEASE_ZIP_SHA256 = 'b6f952c783009b7642720e06d8f5f1781e080497f91b98521aea545cbcb2d86d'

BINANCE_START_DATE = date(2026, 8, 3)
BINANCE_END_DATE = date(2026, 8, 7)

OKX_START_MS = 1785715200000       # 2026-08-03T00:00:00Z
OKX_END_EXCLUSIVE_MS = 1786218900000  # 2026-08-08T19:55:00Z
OKX_STEP_MS = 300_000
OKX_EXPECTED_ROWS = 1679
OKX_LIMIT = 100
OKX_MAX_PAGES = 20


def binance_objects() -> list[dict]:
    old = (binance_base.EXPERIMENT_ID, binance_base.START_DATE, binance_base.END_DATE)
    try:
        binance_base.EXPERIMENT_ID = EXPERIMENT_ID
        binance_base.START_DATE = BINANCE_START_DATE
        binance_base.END_DATE = BINANCE_END_DATE
        return binance_base.frozen_objects()
    finally:
        binance_base.EXPERIMENT_ID, binance_base.START_DATE, binance_base.END_DATE = old


def capture_binance(root: Path, *, fetcher=binance_base.https_get, workers: int = 8) -> dict:
    old = (binance_base.EXPERIMENT_ID, binance_base.START_DATE, binance_base.END_DATE)
    try:
        binance_base.EXPERIMENT_ID = EXPERIMENT_ID
        binance_base.START_DATE = BINANCE_START_DATE
        binance_base.END_DATE = BINANCE_END_DATE
        return binance_base.capture_all(
            Path(root), objects=binance_base.frozen_objects(), fetcher=fetcher, workers=workers
        )
    finally:
        binance_base.EXPERIMENT_ID, binance_base.START_DATE, binance_base.END_DATE = old


def capture_okx(root: Path, *, fetcher=okx_base.https_get) -> dict:
    names = (
        'EXPERIMENT_ID', 'START_MS', 'END_EXCLUSIVE_MS', 'EXPECTED_ROWS',
        'LIMIT', 'MAX_PAGES', 'STEP_MS'
    )
    old = {name: getattr(okx_base, name) for name in names}
    try:
        okx_base.EXPERIMENT_ID = EXPERIMENT_ID
        okx_base.START_MS = OKX_START_MS
        okx_base.END_EXCLUSIVE_MS = OKX_END_EXCLUSIVE_MS
        okx_base.EXPECTED_ROWS = OKX_EXPECTED_ROWS
        okx_base.LIMIT = OKX_LIMIT
        okx_base.MAX_PAGES = OKX_MAX_PAGES
        okx_base.STEP_MS = OKX_STEP_MS
        rep = okx_base.capture_all(Path(root), fetcher=fetcher)
        rep = dict(rep)
        rep['purpose'] = 'Successor-B extended input warmup required for funding_z_21events before ledger start.'
        rep['status'] = 'OKX_B_PREWARMUP_COVERAGE_PROVEN' if rep.get('pass') else 'OKX_B_PREWARMUP_COVERAGE_BLOCKED'
        (Path(root) / 'OKX_B_PREWARMUP_CAPTURE_REPORT.json').write_text(
            json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8'
        )
        return rep
    finally:
        for name, value in old.items():
            setattr(okx_base, name, value)


def capture_all(root: Path, *, binance_fetcher=binance_base.https_get, okx_fetcher=okx_base.https_get, workers: int = 8) -> dict:
    root = Path(root)
    binance = capture_binance(root / 'binance', fetcher=binance_fetcher, workers=workers)
    okx = capture_okx(root / 'okx', fetcher=okx_fetcher)
    passed = bool(binance.get('pass')) and bool(okx.get('pass'))
    report = {
        'schema_version': 1,
        'experiment_id': EXPERIMENT_ID,
        'release_zip_sha256': RELEASE_ZIP_SHA256,
        'purpose': 'Extended pre-ledger input warmup only; ledger/folds/thresholds unchanged.',
        'binance': {
            'date_start': BINANCE_START_DATE.isoformat(),
            'date_end': BINANCE_END_DATE.isoformat(),
            'objects_expected': 20,
            'pass': bool(binance.get('pass')),
        },
        'okx': {
            'start_ms': OKX_START_MS,
            'end_exclusive_ms': OKX_END_EXCLUSIVE_MS,
            'expected_rows': OKX_EXPECTED_ROWS,
            'pass': bool(okx.get('pass')),
        },
        'pass': passed,
        'status': 'SUCCESSOR_B_PREWARMUP_CAPTURED_PENDING_OFFLINE_AUDIT' if passed else 'SUCCESSOR_B_PREWARMUP_CAPTURE_BLOCKED',
        'dataset_coverage_proven': False,
        'flow_alpha_allowed': False,
        'mainnet_authorized': False,
        'order_capability_created': False,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / 'PREWARMUP_CAPTURE_REPORT.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8'
    )
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description='BTC Successor-B extended warmup capture')
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()
    rep = capture_all(Path(args.out), workers=args.workers)
    print(json.dumps(rep, indent=2, sort_keys=True))
    return 0 if rep['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
