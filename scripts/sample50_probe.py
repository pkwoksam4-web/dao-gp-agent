from __future__ import annotations
from urllib.parse import urlencode

FORMAL_BEG='20200601'
FORMAL_END='20260417'


def pure_code(symbol: str) -> str:
    code, exch = symbol.split('.')
    if exch not in {'SZ','SH'} or len(code) != 6 or not code.isdigit():
        raise ValueError(f'bad A-share symbol: {symbol}')
    return code


def sina_symbol(symbol: str) -> str:
    code, exch = symbol.split('.')
    pure_code(symbol)
    return exch.lower() + code


def eastmoney_secid(symbol: str) -> str:
    code, exch = symbol.split('.')
    pure_code(symbol)
    return ('0' if exch == 'SZ' else '1') + '.' + code


def report_url(symbol: str, report_name: str) -> str:
    code = pure_code(symbol)
    params = {
        'reportName': report_name,
        'columns': 'ALL',
        'filter': f'(SECURITY_CODE="{code}")',
        'pageNumber': 1,
        'pageSize': 500,
        'source': 'WEB',
        'client': 'WEB',
    }
    if report_name == 'RPT_SHAREBONUS_DET':
        params['sortColumns'] = 'EX_DIVIDEND_DATE'
        params['sortTypes'] = -1
    return 'https://datacenter-web.eastmoney.com/api/data/v1/get?' + urlencode(params)


def eastmoney_kline_url(symbol: str) -> str:
    params = {
        'secid': eastmoney_secid(symbol),
        'klt': 101,
        'fqt': 0,
        'beg': FORMAL_BEG,
        'end': FORMAL_END,
        'lmt': 5000,
        'ut': '7eea3edcaed734bea9cbfc24409ed989',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
    }
    return 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urlencode(params)


def sohu_history_url(symbol: str) -> str:
    code = pure_code(symbol)
    params = {
        'code': f'cn_{code}',
        'start': FORMAL_BEG,
        'end': FORMAL_END,
        'stat': 1,
        'order': 'D',
        'period': 'd',
        'callback': 'historySearchHandler',
        'rt': 'jsonp',
    }
    return 'https://q.stock.sohu.com/hisHq?' + urlencode(params)
