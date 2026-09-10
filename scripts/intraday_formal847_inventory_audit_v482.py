import re

import pandas as pd


def read_inventory_csv(source):
    """Read inventory metadata without allowing pandas to strip leading zeroes."""
    return pd.read_csv(source, dtype='string', keep_default_na=False)


def norm_symbol(value):
    s = str(value).strip().upper()
    s = s.replace('.XSHE', '.SZ').replace('.XSHG', '.SH')
    if re.fullmatch(r'\d{6}', s):
        return s + ('.SH' if s.startswith(('5', '6', '9')) else '.SZ')
    m = re.fullmatch(r'(SH|SZ)[._-]?(\d{6})', s)
    if m:
        return f'{m.group(2)}.{m.group(1)}'
    m = re.fullmatch(r'(\d{6})[._-]?(SH|SZ)', s)
    if m:
        return f'{m.group(1)}.{m.group(2)}'
    return s


def select_inventory_symbol_column(inv, formal_universe_set):
    candidate_cols = [
        c for c in inv.columns
        if any(k in str(c).lower() for k in ('symbol', 'code', 'ticker', 'instrument'))
    ]
    if not candidate_cols:
        raise ValueError(f'No candidate symbol column in inventory: {list(inv.columns)}')

    col_stats = []
    best_col = None
    best_match = -1
    best_set = set()
    for c in candidate_cols:
        vals = inv[c].map(norm_symbol)
        val_set = {v for v in vals if v}
        matches = len(set(formal_universe_set) & val_set)
        col_stats.append({
            'column': str(c),
            'unique': len(val_set),
            'formal847_matches': matches,
        })
        if matches > best_match:
            best_match = matches
            best_col = c
            best_set = val_set

    return best_col, best_set, col_stats
