from __future__ import annotations

import hashlib
import json
import pathlib
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from global_event_ledger_v481 import validate_ledger_pages

FORMAL_BEG = '2020-06-01'
FORMAL_END = '2026-04-17'
BASE = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36'
OUT = pathlib.Path('artifact_global_event_ledger_v481')
RAW = OUT / 'raw'
RAW.mkdir(parents=True, exist_ok=True)

REPORTS = ('RPT_IPO_ALLOTMENT', 'RPT_SHAREBONUS_DET')


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def url_for(report: str, page: int) -> str:
    params = {
        'reportName': report,
        'columns': 'ALL',
        'pageNumber': page,
        'pageSize': 500,
        'source': 'WEB',
        'client': 'WEB',
        'sortColumns': 'EX_DIVIDEND_DATE',
        'sortTypes': -1,
        'filter': f"(EX_DIVIDEND_DATE>='{FORMAL_BEG}')(EX_DIVIDEND_DATE<='{FORMAL_END}')",
    }
    if report == 'RPT_IPO_ALLOTMENT':
        params['quoteColumns'] = 'f2~01~SECURITY_CODE~NEW_PRICE'
    return BASE + '?' + urlencode(params)


def fetch_page(report: str, page: int) -> dict:
    url = url_for(report, page)
    req = Request(url, headers={'User-Agent': UA, 'Accept': '*/*', 'Referer': 'https://data.eastmoney.com/'})
    with urlopen(req, timeout=40) as r:
        body = r.read()
        status = getattr(r, 'status', 200)
        ctype = r.headers.get('Content-Type')
    if status != 200:
        raise RuntimeError(f'{report} page {page}: HTTP {status}')
    payload = json.loads(body.decode('utf-8'))
    return {
        'report': report,
        'page_number': page,
        'url': url,
        'http_status': status,
        'content_type': ctype,
        'bytes': len(body),
        'sha256': sha256(body),
        'body': body,
        'payload': payload,
    }


def fetch_complete_report(report: str, workers: int = 6) -> tuple[dict, list[dict]]:
    first = fetch_page(report, 1)
    result = (first['payload'].get('result') or {})
    pages = int(result.get('pages') or 0)
    count = int(result.get('count') or 0)
    if first['payload'].get('success') is not True or int(first['payload'].get('code', -1)) != 0:
        raise RuntimeError(f'{report}: first page non-success')
    if pages <= 0 and count > 0:
        raise RuntimeError(f'{report}: invalid pages={pages} count={count}')

    docs = {1: first}
    if pages > 1:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futures = {ex.submit(fetch_page, report, p): p for p in range(2, pages + 1)}
            for f in as_completed(futures):
                p = futures[f]
                docs[p] = f.result()
                if len(docs) % 10 == 0 or len(docs) == pages:
                    print(json.dumps({'report': report, 'pass': 1, 'pages_done': len(docs), 'pages_total': pages}), flush=True)

    ordered = [docs[p] for p in range(1, pages + 1)] if pages else [first]
    validated = validate_ledger_pages(ordered, report, FORMAL_BEG, FORMAL_END)

    for doc in ordered:
        raw_name = f'{report}_page_{doc["page_number"]:03d}.json'
        (RAW / raw_name).write_bytes(doc['body'])
        doc['raw_file'] = 'raw/' + raw_name

    # Second independent pass: require byte-identical pages so pagination did not drift during materialization.
    second_hashes = {}
    if pages:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futures = {ex.submit(fetch_page, report, p): p for p in range(1, pages + 1)}
            for f in as_completed(futures):
                p = futures[f]
                doc2 = f.result()
                second_hashes[p] = doc2['sha256']
    first_hashes = {doc['page_number']: doc['sha256'] for doc in ordered}
    drift_pages = [p for p in sorted(first_hashes) if second_hashes.get(p) != first_hashes[p]]
    if drift_pages:
        raise RuntimeError(f'{report}: second-pass page hash drift at pages {drift_pages[:20]}')

    audit = {
        'report': report,
        'status': validated['status'],
        'formal_window': [FORMAL_BEG, FORMAL_END],
        'page_count': validated['page_count'],
        'row_count': validated['row_count'],
        'api_count': validated['api_count'],
        'unique_security_codes': validated['unique_security_codes'],
        'page_hash_recheck': 'PASS_BYTE_IDENTICAL_TWO_PASS',
        'page_hashes': [
            {
                'page_number': doc['page_number'],
                'sha256': doc['sha256'],
                'bytes': doc['bytes'],
                'content_type': doc['content_type'],
                'url': doc['url'],
                'raw_file': doc['raw_file'],
            }
            for doc in ordered
        ],
    }

    # Preserve source-page provenance on every ledger row.
    with (OUT / f'{report}_FORMAL_LEDGER_V481.jsonl').open('w', encoding='utf-8') as f:
        for doc in ordered:
            for row in (doc['payload'].get('result') or {}).get('data') or []:
                enriched = dict(row)
                enriched['_provenance_report'] = report
                enriched['_provenance_page'] = doc['page_number']
                enriched['_provenance_payload_sha256'] = doc['sha256']
                f.write(json.dumps(enriched, ensure_ascii=False, separators=(',', ':')) + '\n')

    return audit, ordered


def main() -> None:
    audits = []
    for report in REPORTS:
        audit, _ = fetch_complete_report(report)
        audits.append(audit)
        print(json.dumps({'report': report, 'done': True, 'pages': audit['page_count'], 'rows': audit['row_count'], 'status': audit['status']}, ensure_ascii=False), flush=True)

    doc = {
        'artifact': 'GLOBAL_EVENT_LEDGER_V481',
        'version': 'V4.81',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'formal_window': [FORMAL_BEG, FORMAL_END],
        'status': 'GLOBAL_EVENT_LEDGER_EXPLICIT_SUCCESS' if all(a['status'] == 'GLOBAL_LEDGER_EXPLICIT_SUCCESS' and a['page_hash_recheck'] == 'PASS_BYTE_IDENTICAL_TWO_PASS' for a in audits) else 'OPEN',
        'coverage_semantics': 'Complete global filtered ledgers permit absence to serve as negative evidence for the corresponding event family only after all pages pass and second-pass page hashes are byte-identical.',
        'formal_promotion': False,
        'validated_global_provenance_emitted': False,
        'formal_ready': False,
        'oos_metrics_allowed': False,
        'reports': audits,
    }
    (OUT / 'GLOBAL_EVENT_LEDGER_AUDIT_V481.json').write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    if doc['status'] != 'GLOBAL_EVENT_LEDGER_EXPLICIT_SUCCESS':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
