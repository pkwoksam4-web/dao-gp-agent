#!/usr/bin/env python3
import csv
import hashlib

FROZEN_CALENDAR_SHA256 = '0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0'
FROZEN_CALENDAR_N = 1426
FROZEN_CALENDAR_FIRST = '2020-06-01'
FROZEN_CALENDAR_LAST = '2026-04-17'


def derive_verified_calendar(daily_path, expected_sha256=FROZEN_CALENDAR_SHA256,
                             expected_n=FROZEN_CALENDAR_N,
                             expected_first=FROZEN_CALENDAR_FIRST,
                             expected_last=FROZEN_CALENDAR_LAST):
    dates = set()
    with open(daily_path, encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f):
            date = str(row.get('date', '')).strip()
            if date:
                dates.add(date)
    ordered = sorted(dates)
    if len(ordered) != expected_n:
        raise ValueError(f'calendar count mismatch: {len(ordered)} != {expected_n}')
    if not ordered or ordered[0] != expected_first or ordered[-1] != expected_last:
        raise ValueError(f'calendar bounds mismatch: {ordered[:1]}..{ordered[-1:] if ordered else []}')
    canonical = ''.join(date + '\n' for date in ordered).encode('ascii')
    actual = hashlib.sha256(canonical).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f'calendar hash mismatch: {actual} != {expected_sha256}')
    return ordered


def write_calendar_csv(path, dates):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['trade_date'])
        for date in dates:
            w.writerow([date])
