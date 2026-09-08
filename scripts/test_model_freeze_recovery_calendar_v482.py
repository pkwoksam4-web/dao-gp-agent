import hashlib
import unittest

import model_freeze_recovery_v482 as mod


def calendar_csv(dates):
    return 'trade_date\n' + ''.join(f'{date}\n' for date in dates)


class ModelFreezeRecoveryCalendarV482Tests(unittest.TestCase):
    def test_verified_calendar_csv_preserves_legacy_and_semantic_hash_namespaces(self):
        dates = ['2020-06-01', '2020-06-02']
        legacy = hashlib.sha256(b'2020-06-01\n2020-06-02\n').hexdigest()
        semantic = hashlib.sha256(b'2020-06-01\n2020-06-02').hexdigest()
        out = mod.verify_authoritative_calendar_csv(
            calendar_csv(dates),
            expected_n=2,
            expected_first='2020-06-01',
            expected_last='2020-06-02',
            expected_legacy_sha256=legacy,
        )
        self.assertEqual(out['dates'], dates)
        self.assertEqual(out['legacy_frozen_calendar_sha256'], legacy)
        self.assertEqual(out['formal_calendar_sha256'], semantic)
        self.assertNotEqual(out['legacy_frozen_calendar_sha256'], out['formal_calendar_sha256'])

    def test_verified_calendar_csv_rejects_contract_hash_mismatch(self):
        with self.assertRaises(ValueError):
            mod.verify_authoritative_calendar_csv(
                calendar_csv(['2020-06-01', '2020-06-02']),
                expected_n=2,
                expected_first='2020-06-01',
                expected_last='2020-06-02',
                expected_legacy_sha256='0' * 64,
            )

    def test_verified_calendar_csv_rejects_duplicate_or_wrong_bounds(self):
        dates = ['2020-06-01', '2020-06-01']
        legacy = hashlib.sha256(b'2020-06-01\n2020-06-01\n').hexdigest()
        with self.assertRaises(ValueError):
            mod.verify_authoritative_calendar_csv(
                calendar_csv(dates),
                expected_n=2,
                expected_first='2020-06-01',
                expected_last='2020-06-01',
                expected_legacy_sha256=legacy,
            )

        good = ['2020-06-01', '2020-06-02']
        good_legacy = hashlib.sha256(b'2020-06-01\n2020-06-02\n').hexdigest()
        with self.assertRaises(ValueError):
            mod.verify_authoritative_calendar_csv(
                calendar_csv(good),
                expected_n=2,
                expected_first='2020-05-29',
                expected_last='2020-06-02',
                expected_legacy_sha256=good_legacy,
            )


if __name__ == '__main__':
    unittest.main()
