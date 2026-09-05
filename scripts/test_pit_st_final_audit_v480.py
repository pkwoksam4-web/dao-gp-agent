import unittest
from pit_st_final_audit_v480 import audit_symbol_lifecycle, crosscheck_transitions, gate_decision

CAL = ['2025-01-02','2025-01-03','2025-01-06','2025-01-07']

class LifecycleAuditTests(unittest.TestCase):
    def test_active_symbol_requires_all_calendar_dates_from_ipo(self):
        rows=[{'date':d,'tradestatus':'1'} for d in CAL]
        r=audit_symbol_lifecycle('000001.SZ','2020-01-01','',rows,CAL)
        self.assertEqual(r['status'],'PASS_LIFECYCLE_COVERAGE')
        self.assertEqual(r['missing_required_dates'],[])

    def test_interior_gap_is_unknown_not_not_st(self):
        rows=[{'date':'2025-01-02','tradestatus':'1'},{'date':'2025-01-06','tradestatus':'1'},{'date':'2025-01-07','tradestatus':'1'}]
        r=audit_symbol_lifecycle('000001.SZ','2020-01-01','',rows,CAL)
        self.assertEqual(r['status'],'UNKNOWN_COVERAGE_GAP')
        self.assertEqual(r['missing_required_dates'],['2025-01-03'])

    def test_outdate_is_exclusive_for_formal_eligibility(self):
        rows=[
            {'date':'2025-01-02','tradestatus':'1'},
            {'date':'2025-01-03','tradestatus':'1'},
            {'date':'2025-01-06','tradestatus':'0'},
        ]
        r=audit_symbol_lifecycle('000001.SZ','2020-01-01','2025-01-06',rows,CAL)
        self.assertEqual(r['status'],'PASS_LIFECYCLE_COVERAGE')
        self.assertEqual(r['required_dates'],['2025-01-02','2025-01-03'])
        self.assertEqual(r['outdate_bookkeeping_rows'],['2025-01-06'])

    def test_missing_outdate_row_is_not_a_gap(self):
        rows=[{'date':'2025-01-02','tradestatus':'1'},{'date':'2025-01-03','tradestatus':'1'}]
        r=audit_symbol_lifecycle('000001.SZ','2020-01-01','2025-01-06',rows,CAL)
        self.assertEqual(r['status'],'PASS_LIFECYCLE_COVERAGE')
        self.assertEqual(r['missing_required_dates'],[])

    def test_trading_row_on_or_after_outdate_is_invalid(self):
        rows=[
            {'date':'2025-01-02','tradestatus':'1'},
            {'date':'2025-01-03','tradestatus':'1'},
            {'date':'2025-01-06','tradestatus':'1'},
        ]
        r=audit_symbol_lifecycle('000001.SZ','2020-01-01','2025-01-06',rows,CAL)
        self.assertEqual(r['status'],'UNKNOWN_POST_OUTDATE_TRADING')

    def test_pre_ipo_rows_are_invalid_if_trading(self):
        rows=[
            {'date':'2025-01-02','tradestatus':'1'},
            {'date':'2025-01-03','tradestatus':'1'},
        ]
        r=audit_symbol_lifecycle('000001.SZ','2025-01-03','',rows,CAL)
        self.assertEqual(r['status'],'UNKNOWN_PRE_IPO_TRADING')

OBSERVED = {
  '000001.SZ': [
    {'effective_observed_date':'2024-04-29','from_isST':'0','to_isST':'1'},
    {'effective_observed_date':'2025-06-30','from_isST':'1','to_isST':'0'},
  ]
}

class TransitionCrosscheckTests(unittest.TestCase):
    def test_exact_date_and_state_pair_pass(self):
        evidence=[
          {'symbol':'000001.SZ','effective_date':'2024-04-29','from_isST':'0','to_isST':'1','source_url':'https://example.test/a'},
          {'symbol':'000001.SZ','effective_date':'2025-06-30','from_isST':'1','to_isST':'0','source_url':'https://example.test/b'},
        ]
        r=crosscheck_transitions(OBSERVED,evidence)
        self.assertTrue(r['all_pass'])
        self.assertEqual(r['matched_n'],2)

    def test_wrong_date_fails(self):
        evidence=[{'symbol':'000001.SZ','effective_date':'2024-04-30','from_isST':'0','to_isST':'1','source_url':'https://example.test/a'}]
        r=crosscheck_transitions(OBSERVED,evidence)
        self.assertFalse(r['all_pass'])
        self.assertEqual(r['results'][0]['status'],'FAIL_NO_EXACT_OBSERVED_TRANSITION')

    def test_wrong_direction_fails(self):
        evidence=[{'symbol':'000001.SZ','effective_date':'2024-04-29','from_isST':'1','to_isST':'0','source_url':'https://example.test/a'}]
        r=crosscheck_transitions(OBSERVED,evidence)
        self.assertFalse(r['all_pass'])

    def test_missing_source_fails_closed(self):
        evidence=[{'symbol':'000001.SZ','effective_date':'2024-04-29','from_isST':'0','to_isST':'1','source_url':''}]
        r=crosscheck_transitions(OBSERVED,evidence)
        self.assertFalse(r['all_pass'])
        self.assertEqual(r['results'][0]['status'],'FAIL_MISSING_INDEPENDENT_SOURCE')

BASE={
 'scope_n':847,'materialized_symbol_n':847,'unresolved_symbol_n':0,'lifecycle_pass_n':847,
 'calendar_n':1426,'duplicate_daily_keys':0,'invalid_daily_rows':0,'outside_calendar_rows':0,
 'delisted_controls_pass':True,'transition_crosscheck_all_pass':True,
}

class FinalGateTests(unittest.TestCase):
 def test_all_required_checks_close_pit_st_but_not_formal_oos(self):
  r=gate_decision(dict(BASE))
  self.assertTrue(r['pit_st_gate_closed'])
  self.assertFalse(r['formal_ready'])
  self.assertFalse(r['oos_metrics_allowed'])

 def test_any_unresolved_symbol_fails_closed(self):
  x=dict(BASE); x['unresolved_symbol_n']=1
  r=gate_decision(x)
  self.assertFalse(r['pit_st_gate_closed'])

 def test_transition_audit_failure_fails_closed(self):
  x=dict(BASE); x['transition_crosscheck_all_pass']=False
  self.assertFalse(gate_decision(x)['pit_st_gate_closed'])

 def test_lifecycle_shortfall_fails_closed(self):
  x=dict(BASE); x['lifecycle_pass_n']=846
  self.assertFalse(gate_decision(x)['pit_st_gate_closed'])

if __name__=='__main__': unittest.main()
