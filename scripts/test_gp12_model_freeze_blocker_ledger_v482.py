import unittest

from gp12_model_freeze_blocker_ledger_v482 import build_model_freeze_blocker_ledger


HISTORICAL = [
    'COMPLETE_12_FACTOR_STRATEGY_CODE_BYTES_MISSING',
    'EXACT_NON_DAILY_FACTOR_FORMULAS_NORMALIZATION_AGGREGATION_MISSING',
    'FULL_GP12_THREE_WAY_PROBABILITY_MAPPING_MISSING',
    'RANKING_TOPN_SEMANTICS_MISSING',
    'ENTRY_EXIT_THRESHOLDS_MISSING',
    'HOLDING_REBALANCE_POLICY_MISSING',
    'POSITION_SIZING_AND_RISK_RULES_MISSING',
    'ACTUAL_FILL_PRICE_AND_INTRADAY_EXECUTION_RULES_MISSING',
]
MIXED = [
    'PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE',
    'FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING',
]


def checkpoint():
    return {
        'artifact':'GP12_MODEL_FREEZE_PROVENANCE_CHECKPOINT_V482',
        'version':'V4.82','strategy_id':'GP_V11','status':'BLOCKED_MODEL_FREEZE_PROVENANCE',
        'formal_feature_ready':True,'oos_calendar_ready':True,'strategy_provenance_complete':False,
        'candidate_substitution_allowed':False,'model_freeze_allowed':False,'oos_metrics_allowed':False,
        'remaining_blockers':HISTORICAL+MIXED,
    }


def triage():
    return {
        'artifact':'GP12_MODEL_FREEZE_RECOVERY_TRIAGE_V482','version':'V4.82','strategy_id':'GP_V11',
        'status':'RECOVERY_TRIAGED_MODEL_FREEZE_BLOCKED',
        'historical_contract_blockers':HISTORICAL,
        'mixed_data_and_contract_blockers':MIXED,
        'pure_engineering_blockers':[],
        'candidate_substitution_allowed':False,'model_freeze_allowed':False,'oos_metrics_allowed':False,
    }


def sector_fund():
    return {
        'artifact':'GP12_SECTOR_FUND_SOURCE_PROVENANCE_V482','version':'V4.82','strategy_id':'GP_V11',
        'status':'PARTIAL_SOURCE_PROVENANCE_BOUND',
        'blocker':'PIT_SECTOR_AND_FUND_FLOW_INPUT_PROVENANCE_INCOMPLETE','blocker_closed':False,
        'sector':{'adapter_path_recovered':True,'source_snapshot_identity_locked':False,'pit_membership_verified':False},
        'fund_flow':{
            'candidate_snapshot_identity_locked':True,
            'remote_pointer_identity_verified':True,
            'actual_snapshot_bytes_verified_in_current_recovery':True,
            'verified_rows':4934625,
            'verified_symbols':5148,
            'verified_coverage':['2021-01-04','2025-04-23'],
            'verified_payload_size_bytes':2134704074,
            'verified_payload_sha256':'034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea',
            'formal_window_coverage_complete':False,
            'pit_provenance_complete':False,
        },
        'remaining_data_gaps':['SECTOR_SOURCE_SNAPSHOT_IDENTITY_UNBOUND','SECTOR_SOURCE_BYTES_NOT_HASH_BOUND','SECTOR_PIT_MEMBERSHIP_UNVERIFIED','FUND_FLOW_FORMAL_WINDOW_COVERAGE_INCOMPLETE','FUND_FLOW_PIT_KNOWN_AT_UNBOUND'],
        'remaining_contract_gaps':['SECTOR_RS_BREADTH_SLOPE_NORMALIZATION_AND_AGGREGATION_MISSING','PRICE_FUND_EFFICIENCY_FORMULA_PULSE_FILTER_AND_NORMALIZATION_MISSING'],
        'data_completion_would_close_blocker_by_itself':False,
        'model_freeze_allowed':False,'oos_metrics_allowed':False,
    }


def intraday():
    return {
        'artifact':'GP12_INTRADAY_PARTIAL_PROVENANCE_V482','version':'V4.82','strategy_id':'GP_V11',
        'status':'PASS_FORMAL847_15M_60M_COVERAGE_PARTIAL_INTRADAY_PROVENANCE',
        'blocker':'FORMAL847_INTRADAY_BYTE_COVERAGE_AND_HISTORICAL_RESAMPLING_MISSING','blocker_closed':False,
        'exact_gap':{'symbol':'000638.SZ','date':'2026-04-13'},
        'primary_snapshot':{'symbol_n':847,'required_trade_dates':1011607,'valid_trade_dates':1011606,'missing_trade_dates':1,'invalid_grid_dates':0,'bars_15m_rows':16185696,'bars_60m_rows':4046424,'shard_evidence_semantic_sha256':'355502946ab0f769dc43313f7757984e2bac9297cb241df378b875c9de20e39b'},
        'formal_847_15m_coverage_verified':True,'formal_847_60m_coverage_verified':True,
        'formal_847_minute_byte_coverage_verified':False,
        'historical_gp_intraday_resampling_contract_recovered':False,'factor_formula_recovered':False,
        'remaining_subgaps':['FORMAL847_MINUTE_BYTE_COVERAGE_SINGLE_DAY_GAP_000638_SZ_2026_04_13','HISTORICAL_GP_INTRADAY_RESAMPLING_CONTRACT_MISSING','EXACT_INTRADAY_CONFIRMATION_FACTOR_FORMULA_MISSING'],
        'model_freeze_allowed':False,'oos_metrics_allowed':False,
    }


class ModelFreezeBlockerLedgerV482Test(unittest.TestCase):
    def test_ledger_separates_eight_historical_and_two_partial_blockers(self):
        x=build_model_freeze_blocker_ledger(checkpoint(),triage(),sector_fund(),intraday())
        self.assertEqual(x['status'],'BLOCKED_MODEL_FREEZE_PROVENANCE_RECOVERY_PARTIAL')
        self.assertEqual(x['summary'],{'blocker_n':10,'closed_n':0,'partial_recovery_n':2,'historical_contract_missing_n':8})
        by={r['blocker']:r for r in x['blockers']}
        for b in HISTORICAL:
            self.assertEqual(by[b]['recovery_state'],'HISTORICAL_CONTRACT_MISSING')
        self.assertEqual(by[MIXED[0]]['recovery_state'],'PARTIAL_ENGINEERING_RECOVERY')
        self.assertEqual(by[MIXED[1]]['recovery_state'],'PARTIAL_ENGINEERING_RECOVERY')
        sf=by[MIXED[0]]['evidence']
        self.assertTrue(sf['fund_flow_source_bytes_verified'])
        self.assertEqual(sf['fund_flow_verified_rows'],4934625)
        self.assertEqual(sf['fund_flow_verified_symbols'],5148)
        self.assertEqual(sf['fund_flow_verified_coverage'],['2021-01-04','2025-04-23'])
        self.assertEqual(sf['fund_flow_verified_payload_sha256'],'034f6578d1475856c8a74285167e6f167bbb7052d25a1c691d804a9c2bbe6eea')
        self.assertNotIn('FUND_FLOW_SOURCE_BYTES_NOT_VERIFIED_IN_CURRENT_RECOVERY',sf['remaining_data_gaps'])
        self.assertTrue(by[MIXED[1]]['evidence']['formal_847_15m_coverage_verified'])
        self.assertTrue(by[MIXED[1]]['evidence']['formal_847_60m_coverage_verified'])
        self.assertFalse(by[MIXED[1]]['evidence']['formal_847_minute_byte_coverage_verified'])
        self.assertEqual(by[MIXED[1]]['evidence']['exact_gap'],{'symbol':'000638.SZ','date':'2026-04-13'})
        self.assertFalse(x['candidate_substitution_allowed'])
        self.assertFalse(x['model_freeze_allowed'])
        self.assertFalse(x['oos_metrics_allowed'])

    def test_intraday_partial_evidence_cannot_claim_closed_or_minute_complete(self):
        for key in ('blocker_closed','formal_847_minute_byte_coverage_verified','historical_gp_intraday_resampling_contract_recovered','factor_formula_recovered'):
            i=intraday(); i[key]=True
            with self.assertRaisesRegex(ValueError,'intraday'):
                build_model_freeze_blocker_ledger(checkpoint(),triage(),sector_fund(),i)

    def test_sector_fund_partial_evidence_cannot_claim_closed(self):
        s=sector_fund(); s['blocker_closed']=True
        with self.assertRaisesRegex(ValueError,'sector/fund'):
            build_model_freeze_blocker_ledger(checkpoint(),triage(),s,intraday())

    def test_verified_fund_flow_bytes_are_required_for_current_ledger_state(self):
        s=sector_fund(); s['fund_flow']['actual_snapshot_bytes_verified_in_current_recovery']=False
        with self.assertRaisesRegex(ValueError,'sector/fund'):
            build_model_freeze_blocker_ledger(checkpoint(),triage(),s,intraday())

    def test_any_open_oos_or_model_freeze_input_fails(self):
        c=checkpoint(); c['oos_metrics_allowed']=True
        with self.assertRaisesRegex(ValueError,'fail-closed'):
            build_model_freeze_blocker_ledger(c,triage(),sector_fund(),intraday())

    def test_canonical_ten_blocker_set_is_required(self):
        c=checkpoint(); c['remaining_blockers']=c['remaining_blockers'][:-1]
        with self.assertRaisesRegex(ValueError,'canonical blocker'):
            build_model_freeze_blocker_ledger(c,triage(),sector_fund(),intraday())


if __name__=='__main__':
    unittest.main()
