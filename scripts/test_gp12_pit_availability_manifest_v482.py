from __future__ import annotations

import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data' / 'GP12_PIT_EVENT_AVAILABILITY_V482.json'


class PitAvailabilityManifestTests(unittest.TestCase):
    def test_exact_partitions_are_present_and_unique(self):
        self.assertTrue(MANIFEST.is_file(), 'PIT availability manifest is missing')
        x = json.loads(MANIFEST.read_text(encoding='utf-8'))
        nominal = x['nominal_events']
        standard = x['standard_overrides']
        special = x['special_overrides']
        self.assertEqual(len(nominal), 2732)
        self.assertEqual(len(standard), 270)
        self.assertEqual(len(special), 11)
        for rows in (nominal, standard, special):
            keys = [(r['symbol'], r['ex_date']) for r in rows]
            self.assertEqual(len(keys), len(set(keys)))

    def test_all_static_availability_is_no_later_than_ex_date(self):
        x = json.loads(MANIFEST.read_text(encoding='utf-8'))
        for row in x['nominal_events']:
            self.assertLessEqual(row['availability_date'], row['ex_date'])
            self.assertRegex(row['evidence_sha256'], r'^[0-9a-f]{64}$')
        for row in x['standard_overrides']:
            self.assertLessEqual(row['availability_date'], row['ex_date'])
            self.assertRegex(row['pdf_sha256'], r'^[0-9a-f]{64}$')
            self.assertTrue(row['announcement_id'])
        for row in x['special_overrides']:
            self.assertLess(row['formula_availability_date'], row['ex_date'])
            self.assertTrue(row['formula_announcement_id'])
            self.assertTrue(row['formula_pdf_url'].startswith('https://static.cninfo.com.cn/'))
            self.assertRegex(row['final_reference_pdf_sha256'], r'^[0-9a-f]{64}$')

    def test_final_override_keys_are_subsets_of_nominal_event_keys(self):
        x = json.loads(MANIFEST.read_text(encoding='utf-8'))
        nominal = {(r['symbol'], r['ex_date']) for r in x['nominal_events']}
        standard = {(r['symbol'], r['ex_date']) for r in x['standard_overrides']}
        special = {(r['symbol'], r['ex_date']) for r in x['special_overrides']}
        self.assertTrue(standard <= nominal)
        self.assertTrue(special <= nominal)
        self.assertFalse(standard & special)


if __name__ == '__main__':
    unittest.main()
