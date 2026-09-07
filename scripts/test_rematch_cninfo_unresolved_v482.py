import json
import tempfile
import unittest
from pathlib import Path

import rematch_cninfo_unresolved_v482 as mod


def _ann(title, when_ms, url):
    return {
        'announcementTitle': title,
        'announcementTime': when_ms,
        'adjunctUrl': url,
        'announcementId': url,
    }


class OfflineRematchV482Tests(unittest.TestCase):
    def test_rematches_remaining_title_variants_without_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / 'raw'
            raw.mkdir()
            rows = [
                ('000709.SZ', '2024-07-11', 'a.json', [
                    _ann('2023年度分红<em>实施</em><em>公告</em>', 1720108800000, 'annual.pdf'),
                ]),
                ('001323.SZ', '2025-08-21', 'b.json', [
                    _ann('2024年度资本公积金转增股本<em>实施</em><em>公告</em>', 1755187200000, 'cap.pdf'),
                    _ann('关于回购股份<em>实施</em>结果暨股份变动的<em>公告</em>', 1753113600000, 'buyback.pdf'),
                ]),
                ('002014.SZ', '2025-09-30', 'c.json', [
                    _ann('2025年中期现金分红的<em>实施</em><em>公告</em>', 1758556800000, 'cash.pdf'),
                ]),
            ]
            records = []
            for symbol, ex_date, fn, items in rows:
                (raw / fn).write_text(json.dumps({'announcements': items}, ensure_ascii=False), encoding='utf-8')
                records.append({
                    'symbol': symbol,
                    'ex_date': ex_date,
                    'error': None,
                    'match': None,
                    'query': {'raw_file': fn, 'announcement_n': len(items)},
                })
            report = {
                'target_event_n': 3,
                'matched_event_n': 0,
                'unresolved_event_n': 3,
                'records': records,
                'formal_promotion': False,
                'validated_global_provenance_emitted': False,
                'formal_ready': False,
                'oos_metrics_allowed': False,
            }
            (root / 'CNINFO_REMAINING_LOW_RATE_RECOVERY_V482.json').write_text(
                json.dumps(report, ensure_ascii=False), encoding='utf-8'
            )
            out = root / 'out'
            result = mod.rematch_unresolved(root, out)
            self.assertEqual(result['target_event_n'], 3)
            self.assertEqual(result['matched_event_n'], 3)
            self.assertEqual(result['unresolved_event_n'], 0)
            picked = {(r['symbol'], r['ex_date']): r['match']['adjunctUrl'] for r in result['records']}
            self.assertEqual(picked[('000709.SZ', '2024-07-11')], 'annual.pdf')
            self.assertEqual(picked[('001323.SZ', '2025-08-21')], 'cap.pdf')
            self.assertEqual(picked[('002014.SZ', '2025-09-30')], 'cash.pdf')
            self.assertFalse(result['formal_promotion'])
            self.assertFalse(result['formal_ready'])

    def test_unrelated_implementation_title_stays_unmatched(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            raw = root / 'raw'
            raw.mkdir()
            fn = 'x.json'
            (raw / fn).write_text(json.dumps({'announcements': [
                _ann('关于回购股份<em>实施</em>结果暨股份变动的<em>公告</em>', 1753113600000, 'buyback.pdf')
            ]}, ensure_ascii=False), encoding='utf-8')
            report = {
                'target_event_n': 1,
                'matched_event_n': 0,
                'unresolved_event_n': 1,
                'records': [{
                    'symbol': '001323.SZ', 'ex_date': '2025-08-21', 'error': None, 'match': None,
                    'query': {'raw_file': fn, 'announcement_n': 1},
                }],
                'formal_promotion': False,
                'validated_global_provenance_emitted': False,
                'formal_ready': False,
                'oos_metrics_allowed': False,
            }
            (root / 'CNINFO_REMAINING_LOW_RATE_RECOVERY_V482.json').write_text(
                json.dumps(report, ensure_ascii=False), encoding='utf-8'
            )
            result = mod.rematch_unresolved(root, root / 'out')
            self.assertEqual(result['matched_event_n'], 0)
            self.assertEqual(result['unresolved_event_n'], 1)


if __name__ == '__main__':
    unittest.main()
