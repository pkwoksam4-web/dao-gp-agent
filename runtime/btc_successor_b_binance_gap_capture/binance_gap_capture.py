from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.btc_shadow2_archive_capture import archive_capture as base

EXPERIMENT_ID = 'BTC-FLOW-SUCCESSOR-20261009-B'
START_DATE = date(2026, 8, 8)
END_DATE = date(2026, 8, 12)
FAMILIES = base.FAMILIES


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.START_DATE = START_DATE
    base.END_DATE = END_DATE


def frozen_objects() -> list[dict]:
    _configure_base()
    return base.frozen_objects()


def capture_all(root: Path, *, fetcher=base.https_get, workers: int = 8) -> dict:
    _configure_base()
    return base.capture_all(Path(root), objects=frozen_objects(), fetcher=fetcher, workers=workers)


def main() -> int:
    ap = argparse.ArgumentParser(description='BTC Successor-B fixed Binance Data Vision five-day gap capture')
    ap.add_argument('--out', required=True)
    ap.add_argument('--workers', type=int, default=8)
    args = ap.parse_args()
    report = capture_all(Path(args.out), workers=args.workers)
    print(json.dumps({k: report[k] for k in (
        'status', 'pass', 'experiment_id', 'objects_expected', 'objects_passed',
        'objects_failed', 'date_start', 'date_end', 'flow_alpha_allowed'
    )}, indent=2, sort_keys=True))
    return 0 if report['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
