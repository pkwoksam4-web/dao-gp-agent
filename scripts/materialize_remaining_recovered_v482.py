from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed

from cninfo_effective_terms_v481 import extract_effective_terms
from cninfo_exact_term_v481 import announcement_pdf_url
from materialize_standard_exact_pdfs_v481 import _extract_pdf_text, _fetch_pdf

VERSION = 'V4.82'


def select_matched_rows(report: dict) -> list[dict]:
    rows = []
    seen: set[tuple[str, str]] = set()
    for raw in report.get('records') or []:
        if raw.get('error') is not None or raw.get('match') is None:
            continue
        symbol = str(raw.get('symbol') or '').upper()
        ex_date = str(raw.get('ex_date') or '')[:10]
        if not symbol or not ex_date:
            raise ValueError('matched recovery row missing symbol/ex_date')
        key = (symbol, ex_date)
        if key in seen:
            raise ValueError(f'duplicate matched recovery event {key}')
        seen.add(key)
        row = dict(raw)
        row['symbol'] = symbol
        row['ex_date'] = ex_date
        rows.append(row)
    return sorted(rows, key=lambda r: (r['symbol'], r['ex_date']))


def unique_announcements(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        ann = row.get('match') or {}
        key = str(ann.get('announcementId') or ann.get('adjunctUrl') or '').strip()
        if not key:
            raise ValueError(f'{row.get("symbol")} {row.get("ex_date")}: announcement lacks stable id/url')
        if key in out:
            prior_url = str(out[key].get('adjunctUrl') or '')
            new_url = str(ann.get('adjunctUrl') or '')
            if prior_url != new_url:
                raise ValueError(f'conflicting adjunctUrl for announcement key {key}')
        else:
            out[key] = dict(ann)
    return dict(sorted(out.items()))


def _find_unique(root: pathlib.Path, name: str) -> pathlib.Path:
    hits = [p for p in root.rglob(name) if p.is_file()]
    if len(hits) != 1:
        raise FileNotFoundError(f'expected exactly one {name}; found={len(hits)}')
    return hits[0]


def materialize(recovery_dir: pathlib.Path, out_dir: pathlib.Path, workers: int = 6) -> dict:
    recovery = json.loads(_find_unique(recovery_dir, 'CNINFO_REMAINING_LOW_RATE_RECOVERY_V482.json').read_text(encoding='utf-8'))
    if recovery.get('formal_promotion') is not False or recovery.get('validated_global_provenance_emitted') is not False:
        raise ValueError('recovery artifact violated non-Formal guard')
    matched_rows = select_matched_rows(recovery)
    if len(matched_rows) != int(recovery.get('matched_event_n') or 0):
        raise ValueError('matched recovery partition mismatch')
    announcements = unique_announcements(matched_rows)

    raw_dir = out_dir / 'raw_pdf'
    text_dir = out_dir / 'text'
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)

    def fetch_one(key: str, ann: dict) -> tuple[str, dict]:
        url = announcement_pdf_url(ann)
        body, http_status, attempts, error = _fetch_pdf(url)
        suffix = str(ann.get('announcementId') or key).replace('/', '_')
        pdf_path = raw_dir / f'{suffix}.pdf'
        text_path = text_dir / f'{suffix}.txt'
        if body:
            pdf_path.write_bytes(body)
        text_ok = False
        text_error = None
        terms = None
        if body:
            text_ok, text_error = _extract_pdf_text(pdf_path, text_path)
            if text_ok:
                try:
                    terms = extract_effective_terms(text_path.read_text(encoding='utf-8', errors='replace'))
                except Exception as exc:
                    text_error = f'parser:{type(exc).__name__}: {exc}'
        return key, {
            'url': url,
            'http_status': http_status,
            'attempts': attempts,
            'error': error,
            'bytes': len(body),
            'sha256': hashlib.sha256(body).hexdigest() if body else None,
            'pdf_file': pdf_path.name if body else None,
            'text_file': text_path.name if text_ok else None,
            'text_extract_ok': text_ok,
            'text_error': text_error,
            'effective_terms': terms,
        }

    fetched: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        futures = {pool.submit(fetch_one, key, ann): key for key, ann in announcements.items()}
        for i, future in enumerate(as_completed(futures), 1):
            key, result = future.result()
            fetched[key] = result
            if i % 20 == 0 or i == len(futures):
                print(json.dumps({'pdf_progress': i, 'pdf_total': len(futures)}, ensure_ascii=False), flush=True)

    records = []
    for row in matched_rows:
        ann = row['match']
        key = str(ann.get('announcementId') or ann.get('adjunctUrl'))
        records.append({
            'symbol': row['symbol'],
            'ex_date': row['ex_date'],
            'recovery_source': row.get('source'),
            'announcement': ann,
            'pdf_evidence': fetched.get(key),
        })

    pdf_ok = sum((r.get('pdf_evidence') or {}).get('text_extract_ok') is True for r in records)
    effective = sum(
        bool((r.get('pdf_evidence') or {}).get('effective_terms'))
        and any((r['pdf_evidence']['effective_terms'].get(k) is not None) for k in ('cash_per_share', 'cap_ratio'))
        for r in records
    )
    report = {
        'artifact': 'RECOVERED_REMAINING_PDF_EVIDENCE_V482',
        'version': VERSION,
        'source_target_event_n': int(recovery.get('target_event_n') or 0),
        'source_matched_event_n': int(recovery.get('matched_event_n') or 0),
        'source_unresolved_event_n': int(recovery.get('unresolved_event_n') or 0),
        'matched_event_n': len(records),
        'unique_announcement_n': len(announcements),
        'pdf_text_ok_event_n': pdf_ok,
        'effective_term_event_n': effective,
        'records': records,
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'RECOVERED_REMAINING_PDF_EVIDENCE_V482.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in (
        'source_target_event_n','source_matched_event_n','source_unresolved_event_n',
        'matched_event_n','unique_announcement_n','pdf_text_ok_event_n','effective_term_event_n')
    }, ensure_ascii=False, indent=2))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--recovery-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--workers', type=int, default=6)
    args = ap.parse_args()
    materialize(pathlib.Path(args.recovery_dir), pathlib.Path(args.out_dir), args.workers)


if __name__ == '__main__':
    main()
