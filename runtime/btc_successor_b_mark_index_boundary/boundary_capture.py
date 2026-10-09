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
BOUNDARY_DATE = date(2026, 8, 2)
FAMILIES = ('markPriceKlines', 'indexPriceKlines')


def _set_base():
    old = (base.EXPERIMENT_ID, base.START_DATE, base.END_DATE, base.FAMILIES)
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.START_DATE = BOUNDARY_DATE
    base.END_DATE = BOUNDARY_DATE
    base.FAMILIES = FAMILIES
    return old


def _restore(old):
    base.EXPERIMENT_ID, base.START_DATE, base.END_DATE, base.FAMILIES = old


def frozen_objects() -> list[dict]:
    old = _set_base()
    try:
        return base.frozen_objects()
    finally:
        _restore(old)


def capture_all(root: Path, *, fetcher=base.https_get, workers: int = 2) -> dict:
    old = _set_base()
    try:
        return base.capture_all(Path(root), objects=base.frozen_objects(), fetcher=fetcher, workers=workers)
    finally:
        _restore(old)


def main() -> int:
    ap = argparse.ArgumentParser(description='BTC Successor-B mark/index left-boundary raw capture')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    rep = capture_all(Path(args.out))
    print(json.dumps({k: rep[k] for k in ('status','pass','objects_expected','objects_passed','objects_failed','flow_alpha_allowed')}, indent=2, sort_keys=True))
    return 0 if rep['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
