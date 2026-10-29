import unittest
from w1_snapshot import (canonical_hash, normalize_bao_row, derive_d_status,
                         compare_longbridge, make_snapshot, expected_holdout_dates,
                         SUNSET_HOLDOUT_LABEL)

ROW = {
    'date':'2026-10-29', 'code':'sh.600392', 'open':'10.00',
    'high':'10.20', 'low':'9.90', 'close':'10.10', 'preclose':'10.00',
    'volume':'10000', 'amount':'100500', 'adjustflag':'3',
    'tradestatus':'1', 'isST':'0'
}
class TestW1SnapshotContract(unittest.TestCase):
    def test_symbol_and_unadjusted(self):
        r=normalize_bao_row('600392.SH',ROW)
        self.assertEqual(r['symbol'],'600392.SH')
        self.assertEqual(r['close'],'10.10')
        self.assertEqual(r['volume_shares'],'10000')
        with self.assertRaises(ValueError):
            normalize_bao_row('600392.SH',dict(ROW,adjustflag='2'))
        with self.assertRaises(ValueError):
            normalize_bao_row('600392.SH',dict(ROW,code='sz.600392'))

    def test_d_status_fails_closed_without_official_limit(self):
        r=normalize_bao_row('600392.SH',ROW)
        s=derive_d_status(r,known_at='2026-10-29T15:00:00+08:00',official_up_limit=None)
        self.assertFalse(s['is_st'])
        self.assertTrue(s['tradable'])
        self.assertIsNone(s['upper_limit'])
        self.assertIsNone(s['status_entry_eligible'])
        self.assertEqual(s['status_contract'],'D_UPPER_LIMIT_SOURCE_UNBOUND')

    def test_halted_is_not_upper_limit_event(self):
        r=normalize_bao_row('600392.SH',dict(ROW,tradestatus='0',volume='0',amount='0'))
        s=derive_d_status(r,'2026-10-29T15:00:00+08:00')
        self.assertFalse(s['tradable'])
        self.assertFalse(s['upper_limit'])
        self.assertFalse(s['status_entry_eligible'])

    def test_status_known_at_not_before_close(self):
        r=normalize_bao_row('600392.SH',ROW)
        with self.assertRaises(ValueError):
            derive_d_status(r,'2026-10-29T14:59:00+08:00')

    def test_d_price_limit_exact_decimals_when_authoritative(self):
        r=normalize_bao_row('600392.SH',ROW)
        s=derive_d_status(r,'2026-10-29T15:00:00+08:00',
                          official_up_limit='10.10',verified_official_limit=True,
                          d_isst_authority=True)
        self.assertTrue(s['upper_limit'])
        self.assertFalse(s['status_entry_eligible'])

    def test_hash_deterministic_no_floats(self):
        r=normalize_bao_row('600392.SH',ROW)
        s=normalize_bao_row('000636.SZ',dict(ROW,code='sz.000636'))
        self.assertEqual(canonical_hash([r,s]),canonical_hash([s,r]))
        self.assertEqual(len(canonical_hash([r,s])),64)

    def test_longbridge_utc_date_marker_and_mismatch(self):
        r=normalize_bao_row('600392.SH',ROW)
        same=dict(symbol='600392.SH',timestamp='2026-10-28T16:00:00Z',
                  open='10.00',high='10.20',low='9.90',close='10.10')
        s=compare_longbridge(r,same)
        self.assertEqual(s['status'],'MATCH')
        self.assertEqual(s['local_trade_date'],'2026-10-29')
        self.assertEqual(compare_longbridge(r,dict(same,close='10.11'))['status'],'MISMATCH')
        self.assertEqual(compare_longbridge(r,dict(same,timestamp='2026-10-27T16:00:00Z'))['status'],'STALE_DATE')

    def test_missing_rows_reported_not_forward_filled(self):
        r=normalize_bao_row('600392.SH',ROW)
        s=make_snapshot('2026-10-29',['600392.SH','000636.SZ'],[r],
                        '2026-10-29T18:40:00+08:00',{'600392.SH':{'status':'MATCH'}})
        self.assertEqual(s['state'],'INCOMPLETE')
        self.assertEqual(s['missing_symbols'],['000636.SZ'])
        self.assertEqual(s['holdout'],SUNSET_HOLDOUT_LABEL)
        self.assertNotIn('rows',s)

    def test_holdout_boundary_uses_sessions_not_calendar_days(self):
        days=['2026-04-17','2026-04-20','2026-04-21']
        self.assertEqual(expected_holdout_dates(days),['2026-04-20','2026-04-21'])

    def test_duplicate_fails_closed(self):
        r=normalize_bao_row('600392.SH',ROW)
        with self.assertRaises(ValueError):
            make_snapshot('2026-10-29',['600392.SH'],[r,r],
                          '2026-10-29T18:40:00+08:00',{})

if __name__=='__main__':unittest.main()
