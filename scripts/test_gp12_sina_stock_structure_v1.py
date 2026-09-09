import unittest
from unittest import mock

import gp12_sina_stock_structure_v1 as mod


def html_bytes(change_dates=None, announcement_dates=None, reasons=None, amounts=None):
    change_dates = change_dates or ['20241231', '20250331']
    announcement_dates = announcement_dates or ['20250104', '20250403']
    reasons = reasons or ['债转股', '债转股']
    amounts = amounts or ['2935217.83 万股', '2935217.900 万股']
    rows = [
        ['变动日期', *change_dates],
        ['公告日期', *announcement_dates],
        ['变动原因', *reasons],
        ['流通A股(历史记录)', *amounts],
    ]
    body = ''.join(
        '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
        for row in rows
    )
    return f'<html><body><table>{body}</table></body></html>'.encode('gb18030')


class SinaStockStructureV1Tests(unittest.TestCase):
    def test_parse_stock_structure_columns(self):
        rows = mod.parse_stock_structure_bytes('600000.SH', html_bytes())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], {
            'symbol': '600000.SH',
            'change_date': '2024-12-31',
            'announcement_date': '2025-01-04',
            'change_reason': '债转股',
            'circulating_a_10k_display': '2935217.83',
            'circulating_a_display_scale': 2,
        })
        self.assertEqual(rows[1]['circulating_a_10k_display'], '2935217.900')
        self.assertEqual(rows[1]['circulating_a_display_scale'], 3)

    def test_real_page_style_pre_circulation_placeholder_is_skipped(self):
        rows = mod.parse_stock_structure_bytes(
            '600000.SH',
            html_bytes(
                change_dates=['20011231', '20000112', '19991110', '19990923'],
                announcement_dates=['19000101', '19000101', '19000101', '19000101'],
                reasons=['其他', '其他', '上市', '发行前'],
                amounts=['40000 万股', '40000 万股', '32000 万股', '--'],
            ),
        )
        self.assertEqual(
            [row['change_date'] for row in rows],
            ['1999-11-10', '2000-01-12', '2001-12-31'],
        )
        self.assertEqual(rows[0]['circulating_a_10k_display'], '32000')

    def test_placeholder_after_first_valid_chronological_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'placeholder'):
            mod.parse_stock_structure_bytes(
                '600000.SH',
                html_bytes(
                    change_dates=['20011231', '20000112', '19991110'],
                    announcement_dates=['19000101', '19000101', '19000101'],
                    reasons=['其他', '其他', '上市'],
                    amounts=['40000 万股', '--', '32000 万股'],
                ),
            )

    def test_missing_announcement_row_is_rejected(self):
        raw = html_bytes().decode('gb18030').replace(
            '<tr><td>公告日期</td><td>20250104</td><td>20250403</td></tr>', '')
        with self.assertRaisesRegex(ValueError, 'announcement'):
            mod.parse_stock_structure_bytes('600000.SH', raw.encode('gb18030'))

    def test_malformed_yyyymmdd_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'date'):
            mod.parse_stock_structure_bytes(
                '600000.SH',
                html_bytes(change_dates=['2024-12-31', '20250331']),
            )

    def test_nonpositive_circulating_a_value_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'circulating'):
            mod.parse_stock_structure_bytes(
                '600000.SH',
                html_bytes(amounts=['0 万股', '2935217.900 万股']),
            )

    def test_unequal_column_counts_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'column'):
            mod.parse_stock_structure_bytes(
                '600000.SH',
                html_bytes(announcement_dates=['20250104']),
            )

    def test_duplicate_normalized_columns_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            mod.parse_stock_structure_bytes(
                '600000.SH',
                html_bytes(
                    change_dates=['20241231', '20241231'],
                    announcement_dates=['20250104', '20250104'],
                    reasons=['债转股', '债转股'],
                    amounts=['2935217.83 万股', '2935217.83 万股'],
                ),
            )

    def test_fetch_success_returns_exact_bytes_and_metadata(self):
        response = mock.Mock()
        response.status_code = 200
        response.content = html_bytes()
        response.raise_for_status.return_value = None
        session = mock.Mock()
        session.get.return_value = response
        raw, meta = mod.fetch_stock_structure(session, '600000.SH', retries=1)
        self.assertEqual(raw, response.content)
        self.assertEqual(meta['status'], 'FETCHED')
        self.assertEqual(meta['http_status'], 200)
        self.assertEqual(meta['symbol'], '600000.SH')
        self.assertEqual(meta['source_endpoint_family'], 'SINA_STOCK_STRUCTURE_HISTORY')
        self.assertEqual(meta['blockers'], [])

    def test_fetch_failure_is_normalized(self):
        session = mock.Mock()
        session.get.side_effect = RuntimeError('network down')
        raw, meta = mod.fetch_stock_structure(session, '600000.SH', retries=1)
        self.assertIsNone(raw)
        self.assertEqual(meta['status'], 'BLOCKED')
        self.assertEqual(meta['blockers'], ['SINA_STOCK_STRUCTURE_SOURCE_UNAVAILABLE'])


if __name__ == '__main__':
    unittest.main()
