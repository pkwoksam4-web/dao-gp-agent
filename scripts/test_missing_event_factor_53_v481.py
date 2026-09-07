import unittest

from run_missing_event_factor_recalc_53_v481 import (
    action_from_base_event,
    build_combined_actions,
)


class Remaining53ActionTests(unittest.TestCase):
    def test_base_global_ledger_event_preserves_terms(self):
        ev={
            'ex_date':'2024-05-10','cash_per_share_nominal':2.078,'stock_ratio':0.0,
            'capitalization_ratio':0.0,'rights_ratio':0.0,'rights_price':None,
            'source':'EASTMONEY_RPT_SHAREBONUS_DET',
        }
        a=action_from_base_event('000538.SZ',ev)
        self.assertEqual(a.symbol,'000538.SZ')
        self.assertEqual(a.ex_date,'2024-05-10')
        self.assertAlmostEqual(a.cash_per_share,2.078)

    def test_mixed_symbol_combines_existing_and_missing_events_exactly(self):
        base={
            'symbol':'000538.SZ',
            'events':[{
                'ex_date':'2024-05-10','cash_per_share_nominal':2.078,'stock_ratio':0.0,
                'capitalization_ratio':0.0,'rights_ratio':0.0,'rights_price':None,
                'source':'EASTMONEY_RPT_SHAREBONUS_DET',
            }],
            'sina_event_dates':['2024-05-10','2024-11-25'],
            'missing_in_ledger':['2024-11-25'],
        }
        f10={
            'symbol':'000538.SZ',
            'targets':[{
                'date':'2024-11-25','status':'F10_PAGEAJAX_TARGET_DATE_HIT',
                'hits':[{'row':{
                    'EX_DIVIDEND_DATE':'2024-11-25 00:00:00','ASSIGN_PROGRESS':'实施方案',
                    'IMPL_PLAN_PROFILE':'10派12.13元',
                }}],
            }],
        }
        actions,evidence=build_combined_actions('000538.SZ',base,f10)
        self.assertEqual([a.ex_date for a in actions],['2024-05-10','2024-11-25'])
        self.assertEqual(evidence['coverage_complete'],True)
        self.assertEqual(evidence['new_profiles'],{'2024-11-25':'10派12.13元'})

    def test_missing_or_nonimplemented_target_fails_closed(self):
        base={
            'symbol':'000430.SZ','events':[],
            'sina_event_dates':['2025-12-29'],'missing_in_ledger':['2025-12-29'],
        }
        f10={'symbol':'000430.SZ','targets':[{
            'date':'2025-12-29','status':'F10_PAGEAJAX_TARGET_DATE_HIT',
            'hits':[{'row':{
                'EX_DIVIDEND_DATE':'2025-12-29 00:00:00','ASSIGN_PROGRESS':'预案',
                'IMPL_PLAN_PROFILE':'10转10',
            }}],
        }]}
        with self.assertRaises(ValueError):
            build_combined_actions('000430.SZ',base,f10)


if __name__=='__main__':
    unittest.main()
