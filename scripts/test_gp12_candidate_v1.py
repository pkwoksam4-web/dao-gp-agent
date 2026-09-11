import copy
import datetime as dt
import importlib
import json
import math
import pathlib
import tempfile
import unittest


mod = importlib.import_module('gp12_candidate_v1')


ROOT = pathlib.Path(__file__).resolve().parents[1]
PARAMETERS_PATH = ROOT / 'data' / 'GP12_CANDIDATE_PARAMETERS_V1.json'
FACTORS_PATH = ROOT / 'data' / 'GP12_CANDIDATE_FACTORS_V1.json'
SHANGHAI = dt.timezone(dt.timedelta(hours=8))


def market_dates(count=121, end=dt.date(2026, 4, 17)):
    dates = []
    cursor = end
    while len(dates) < count:
        if cursor.weekday() < 5:
            dates.append(cursor)
        cursor -= dt.timedelta(days=1)
    return list(reversed(dates))


def valid_snapshot(growth=0.0, scale=1.0):
    dates = market_dates()
    closes = [scale * (1.0 + growth) ** i for i in range(121)]
    daily = []
    for date, close in zip(dates, closes):
        daily.append({
            'date': date.isoformat(),
            'known_at': f'{date.isoformat()}T15:00:00+08:00',
            'close': close,
            'market_close': close,
            'sector_close': close,
            'amount_cny': 100_000_000.0 * scale,
            'turnover_ratio': 0.02,
            'main_net_flow_cny': 0.0,
            'market_breadth_ratio': 0.5,
            'sector_breadth_ratio': 0.5,
        })
    final = dates[-1].isoformat()
    bars15 = [
        {'close': closes[-1], 'closed_at': f'{final}T{hour}+08:00',
         'known_at': f'{final}T{hour}+08:00'}
        for hour in ('14:00:00', '14:15:00', '14:30:00', '14:45:00', '15:00:00')
    ]
    bars60 = [
        {'close': closes[-1], 'closed_at': f'{final}T{hour}+08:00',
         'known_at': f'{final}T{hour}+08:00'}
        for hour in ('10:00:00', '11:00:00', '12:00:00', '13:00:00', '15:00:00')
    ]
    return {
        'strategy_id': 'GP12_REBUILD_CANDIDATE_V1',
        'symbol': '000001.SZ',
        'sector_id': 'BANKS',
        'as_of': f'{final}T15:30:00+08:00',
        'calendar': [date.isoformat() for date in dates],
        'daily': daily,
        'status': {
            'known_at': f'{final}T15:00:00+08:00',
            'is_st': False,
            'tradable': True,
            'upper_limit': False,
        },
        'intraday_15m': bars15,
        'intraday_60m': bars60,
        'source_ids': {
            'market_calendar': 'calendar-fixture',
            'stock_adjusted_close': 'stock-fixture',
            'market_adjusted_close': 'market-fixture',
            'sector_adjusted_close': 'sector-fixture',
            'amount_turnover': 'turnover-fixture',
            'main_net_flow': 'flow-fixture',
            'market_breadth': 'market-breadth-fixture',
            'sector_breadth': 'sector-breadth-fixture',
            'status': 'status-fixture',
            'intraday_15m': '15m-fixture',
            'intraday_60m': '60m-fixture',
        },
    }


def parameters():
    with PARAMETERS_PATH.open(encoding='utf-8') as handle:
        return json.load(handle)


def score_bundle(symbol, sector, score, snapshot_date='2026-04-17'):
    snapshot = valid_snapshot(growth=0.01)
    snapshot['symbol'] = symbol
    snapshot['sector_id'] = sector
    out = mod.score_snapshot(snapshot, parameters())
    out['score'] = score
    return out


class ScoringTests(unittest.TestCase):
    def test_feature_readiness_reports_structure_separately_from_provenance(self):
        raw_fields = {'symbol', 'date', 'open', 'high', 'low', 'close',
                      'volume', 'amount', 'source'}
        raw_gap = mod.raw_panel_gap_report(raw_fields)
        self.assertTrue(raw_gap['raw_schema_complete'])
        self.assertIn('main_net_flow',
                      raw_gap['candidate_families_unrepresented_by_raw_panel'])

        report = mod.feature_input_readiness(valid_snapshot(), raw_fields)
        self.assertTrue(report['structural_input_contract_complete'])
        self.assertEqual(report['missing_families'], [])
        self.assertTrue(report['source_ids_present'])
        self.assertFalse(report['source_ids_substantively_verified'])
        self.assertFalse(report['real_feature_inputs_validated'])
        self.assertEqual(report['raw_panel_gap'], raw_gap)

        no_source_id = valid_snapshot()
        no_source_id['source_ids'].pop('main_net_flow')
        report = mod.feature_input_readiness(no_source_id)
        self.assertFalse(report['structural_input_contract_complete'])
        self.assertEqual(report['missing_families'], [])
        self.assertFalse(report['source_ids_present'])

        incomplete = valid_snapshot()
        incomplete['daily'][-1].pop('turnover_ratio')
        incomplete['source_ids'].pop('main_net_flow')
        report = mod.feature_input_readiness(incomplete)
        self.assertFalse(report['structural_input_contract_complete'])
        self.assertEqual(report['missing_families'], ['amount_turnover'])
        self.assertFalse(report['source_ids_present'])

    def test_flat_fixture_has_twelve_neutral_factors_and_cannot_enter(self):
        result = mod.score_snapshot(valid_snapshot(), parameters())
        self.assertEqual(result['strategy_id'], 'GP12_REBUILD_CANDIDATE_V1')
        self.assertEqual(result['proposal_status'], 'UNAPPROVED')
        self.assertEqual(result['score'], 50.0)
        self.assertEqual(result['factors'], {f'F{i}': 50.0 for i in range(1, 13)})
        self.assertEqual(result['eligibility_exclusions'], ['NONPOSITIVE_20D_MOMENTUM'])
        self.assertEqual(mod.rank_candidates([result], parameters()), [])

    def test_one_percent_exponential_path_has_perfect_positive_er_and_trend(self):
        result = mod.score_snapshot(valid_snapshot(growth=0.01), parameters())
        self.assertEqual(result['raw_factors']['F9'], 1.0)
        self.assertEqual(result['factors']['F9'], 100.0)
        self.assertAlmostEqual(result['trend_diagnostics']['stock_60d_r_squared'], 1.0)
        self.assertEqual(result['factors']['F8'], 100.0)
        self.assertGreater(result['momentum_20d'], 0.0)

    def test_opposite_trend_preserves_signed_efficiency(self):
        result = mod.score_snapshot(valid_snapshot(growth=-0.01), parameters())
        self.assertEqual(result['raw_factors']['F9'], -1.0)
        self.assertEqual(result['factors']['F9'], 0.0)
        self.assertEqual(result['factors']['F8'], 0.0)

    def test_price_and_currency_scale_do_not_change_factors(self):
        base = mod.score_snapshot(valid_snapshot(growth=0.002, scale=1.0), parameters())
        scaled = mod.score_snapshot(valid_snapshot(growth=0.002, scale=100.0), parameters())
        self.assertEqual(base['factors'], scaled['factors'])
        self.assertEqual(base['score'], scaled['score'])

    def test_isolated_fund_pulse_is_clipped_before_averaging(self):
        modest = valid_snapshot(growth=0.002)
        huge = copy.deepcopy(modest)
        modest['daily'][-3]['main_net_flow_cny'] = 20_000_000.0
        huge['daily'][-3]['main_net_flow_cny'] = 100_000_000.0
        a = mod.score_snapshot(modest, parameters())
        b = mod.score_snapshot(huge, parameters())
        self.assertEqual(a['raw_factors']['F11'], b['raw_factors']['F11'])

    def test_liquidity_uses_median_not_mean(self):
        snapshot = valid_snapshot(growth=0.002)
        for row in snapshot['daily'][-20:]:
            row['amount_cny'] = 70_000_000.0
        snapshot['daily'][-1]['amount_cny'] = 400_000_000.0
        result = mod.score_snapshot(snapshot, parameters())
        self.assertGreater(sum(r['amount_cny'] for r in snapshot['daily'][-20:]) / 20, 80_000_000)
        self.assertEqual(result['liquidity_20d_median_cny'], 70_000_000.0)
        self.assertIn('LOW_LIQUIDITY', result['eligibility_exclusions'])

    def test_snapshot_rejects_bad_numeric_values_and_booleans(self):
        mutations = [
            ('missing', lambda s: s['daily'][-1].pop('turnover_ratio')),
            ('nan', lambda s: s['daily'][-1].__setitem__('amount_cny', math.nan)),
            ('boolean', lambda s: s['daily'][-1].__setitem__('close', True)),
            ('zero_price', lambda s: s['daily'][-1].__setitem__('close', 0.0)),
            ('bad_flow', lambda s: s['daily'][-1].__setitem__('main_net_flow_cny', 200_000_000.0)),
            ('bad_breadth', lambda s: s['daily'][-1].__setitem__('market_breadth_ratio', 1.01)),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                snapshot = valid_snapshot()
                mutate(snapshot)
                with self.assertRaises(ValueError):
                    mod.score_snapshot(snapshot, parameters())

    def test_snapshot_rejects_calendar_misalignment_duplicates_and_extra_labels(self):
        mutations = [
            lambda s: s['calendar'].__setitem__(-1, s['calendar'][-2]),
            lambda s: s['daily'][-1].__setitem__('date', s['daily'][-2]['date']),
            lambda s: s.__setitem__('outcome', 'UP'),
            lambda s: s['daily'][-1].__setitem__('future_return', 0.1),
        ]
        for mutate in mutations:
            snapshot = valid_snapshot()
            mutate(snapshot)
            with self.assertRaises(ValueError):
                mod.score_snapshot(snapshot, parameters())

    def test_snapshot_rejects_future_oos_unknown_status_and_stale_intraday(self):
        cases = []
        future = valid_snapshot()
        future['daily'][-1]['known_at'] = '2026-04-17T16:00:00+08:00'
        cases.append(future)
        oos = valid_snapshot()
        oos['calendar'][-1] = '2026-04-20'
        oos['daily'][-1]['date'] = '2026-04-20'
        oos['daily'][-1]['known_at'] = '2026-04-20T15:00:00+08:00'
        oos['as_of'] = '2026-04-20T15:30:00+08:00'
        cases.append(oos)
        unknown = valid_snapshot()
        unknown['status']['is_st'] = None
        cases.append(unknown)
        stale = valid_snapshot()
        stale['intraday_15m'][-1]['closed_at'] = '2026-04-16T15:00:00+08:00'
        stale['intraday_15m'][-1]['known_at'] = '2026-04-16T15:00:00+08:00'
        cases.append(stale)
        for snapshot in cases:
            with self.assertRaises(ValueError):
                mod.score_snapshot(snapshot, parameters())


class RankingAndExitTests(unittest.TestCase):
    def test_ranking_is_stable_and_applies_name_sector_and_total_caps(self):
        rows = [score_bundle(f'{i:06d}.SZ', 'BANKS' if i <= 3 else f'S{i}', 80.0)
                for i in range(1, 13)]
        ranked = mod.rank_candidates(list(reversed(rows)), parameters())
        self.assertEqual([row['symbol'] for row in ranked[:3]],
                         ['000001.SZ', '000002.SZ', '000003.SZ'])
        self.assertEqual(len(ranked), 10)
        self.assertEqual(ranked[0]['research_weight'], 0.1)
        self.assertEqual(ranked[1]['research_weight'], 0.1)
        self.assertEqual(ranked[2]['research_weight'], 0.0)
        self.assertLessEqual(sum(row['research_weight'] for row in ranked), 1.0)

    def test_ranking_rejects_duplicates_mixed_dates_and_parameter_identity_mismatch(self):
        a = score_bundle('000001.SZ', 'BANKS', 80.0)
        duplicate = copy.deepcopy(a)
        mixed = score_bundle('000002.SZ', 'BANKS', 80.0)
        mixed['snapshot_date'] = '2026-04-16'
        mismatch = score_bundle('000003.SZ', 'BANKS', 80.0)
        mismatch['parameter_sha256'] = '0' * 64
        for rows in ([a, duplicate], [a, mixed], [a, mismatch]):
            with self.assertRaises(ValueError):
                mod.rank_candidates(rows, parameters())

    def test_ranking_applies_score_and_status_exclusions(self):
        cases = []
        low_score = score_bundle('000001.SZ', 'A', 59.999)
        cases.append(low_score)
        for field in ('is_st', 'upper_limit'):
            snapshot = valid_snapshot(growth=0.01)
            snapshot['symbol'] = field
            snapshot['status'][field] = True
            cases.append(mod.score_snapshot(snapshot, parameters()))
        snapshot = valid_snapshot(growth=0.01)
        snapshot['symbol'] = 'halted'
        snapshot['status']['tradable'] = False
        cases.append(mod.score_snapshot(snapshot, parameters()))
        self.assertEqual(mod.rank_candidates(cases, parameters()), [])

    def test_exit_boundaries_are_exact(self):
        base = {
            'strategy_id': 'GP12_REBUILD_CANDIDATE_V1',
            'symbol': '000001.SZ',
            'entry_close': 100.0,
            'current_close': 92.0,
            'market_sessions_held': 3,
        }
        self.assertEqual(
            mod.exit_reasons(base, 44.999, parameters()),
            ['SCORE_BELOW_EXIT', 'ADVERSE_MOVE_THRESHOLD', 'MAX_HOLDING_SESSIONS'],
        )
        inside = dict(base, current_close=92.0001, market_sessions_held=2)
        self.assertEqual(mod.exit_reasons(inside, 45.0, parameters()), [])

    def test_exit_rejects_boolean_numeric_inputs(self):
        position = {
            'strategy_id': 'GP12_REBUILD_CANDIDATE_V1', 'symbol': '000001.SZ',
            'entry_close': 100.0, 'current_close': 99.0, 'market_sessions_held': True,
        }
        with self.assertRaises(ValueError):
            mod.exit_reasons(position, 50.0, parameters())


def labelled_rows(count=30, outcome_cycle=('UP', 'DOWN', 'FLAT')):
    rows = []
    for i in range(count):
        day = dt.date(2026, 1, 2) + dt.timedelta(days=i)
        rows.append({
            'symbol': f'{i:06d}.SZ',
            'signal_at': f'{day.isoformat()}T15:30:00+08:00',
            'label_end_at': f'{(day + dt.timedelta(days=1)).isoformat()}T15:00:00+08:00',
            'label_known_at': f'{(day + dt.timedelta(days=1)).isoformat()}T15:30:00+08:00',
            'label_source_id': 'formal-label-fixture',
            'horizon': 2,
            'score': 65.0,
            'outcome': outcome_cycle[i % len(outcome_cycle)],
        })
    return rows


class ProbabilityTests(unittest.TestCase):
    def test_probability_mapping_uses_hand_counted_add_one_smoothing(self):
        rows = labelled_rows(30, ('UP', 'UP', 'DOWN'))
        result = mod.probability_lookup(rows, 69.9, 2, '2026-04-17T16:00:00+08:00')
        self.assertTrue(result['available'])
        self.assertEqual(result['sample_count'], 30)
        self.assertEqual(result['score_decile'], 6)
        self.assertEqual(result['probabilities'], {
            'UP': 21 / 33, 'DOWN': 11 / 33, 'FLAT': 1 / 33,
        })
        self.assertEqual(result['label_source_boundary'], ['formal-label-fixture'])

    def test_probability_mapping_reports_unavailable_below_thirty(self):
        result = mod.probability_lookup(
            labelled_rows(29), 65.0, 2, '2026-04-17T16:00:00+08:00')
        self.assertFalse(result['available'])
        self.assertIsNone(result['probabilities'])
        self.assertEqual(result['sample_count'], 29)

    def test_probability_validates_every_row_before_filtering(self):
        rows = labelled_rows(30)
        future_other_horizon = copy.deepcopy(rows[0])
        future_other_horizon['symbol'] = '999999.SZ'
        future_other_horizon['horizon'] = 1
        future_other_horizon['label_known_at'] = '2026-04-18T15:30:00+08:00'
        rows.append(future_other_horizon)
        with self.assertRaises(ValueError):
            mod.probability_lookup(rows, 65.0, 2, '2026-04-17T16:00:00+08:00')

    def test_probability_rejects_duplicates_oos_and_boolean_score(self):
        rows = labelled_rows(30)
        duplicate = rows + [copy.deepcopy(rows[0])]
        with self.assertRaises(ValueError):
            mod.probability_lookup(duplicate, 65.0, 2, '2026-04-17T16:00:00+08:00')
        with self.assertRaises(ValueError):
            mod.probability_lookup(rows, 65.0, 2, '2026-04-18T00:00:00+08:00')
        with self.assertRaises(ValueError):
            mod.probability_lookup(rows, True, 2, '2026-04-17T16:00:00+08:00')


class PackageReviewTests(unittest.TestCase):
    def test_review_hashes_exact_assets_but_never_admits_candidate(self):
        result = mod.review_package(PARAMETERS_PATH, FACTORS_PATH)
        self.assertEqual(result['status'], 'CANDIDATE_READY_FOR_REVIEW')
        self.assertEqual(result['adoption_status'], 'UNAPPROVED')
        self.assertEqual(result['blockers'], ['NEW_STRATEGY_ADOPTION_REQUIRED'])
        self.assertFalse(result['historical_strategy_recovered'])
        self.assertFalse(result['model_freeze_allowed'])
        self.assertFalse(result['oos_metrics_allowed'])
        self.assertTrue(result['candidate_review_passed'])
        self.assertEqual(set(result['asset_hashes']), {
            'strategy_code_sha256', 'parameter_sha256', 'factor_definition_sha256'})
        self.assertTrue(all(len(value) == 64 for value in result['asset_hashes'].values()))
        self.assertFalse(result['real_feature_inputs_validated'])
        self.assertFalse(result['real_calibration_fitted'])

    def test_review_fails_closed_on_formula_or_parameter_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            factors = json.loads(FACTORS_PATH.read_text(encoding='utf-8'))
            factors['factors'][0]['formula_id'] = 'unsupported'
            factor_path = tmp / 'factors.json'
            factor_path.write_text(json.dumps(factors), encoding='utf-8')
            result = mod.review_package(PARAMETERS_PATH, factor_path)
            self.assertEqual(result['status'], 'CANDIDATE_PACKAGE_INVALID')
            self.assertFalse(result['candidate_review_passed'])
            self.assertIn('FACTOR_CONTRACT_INVALID', result['blockers'])

            params = json.loads(PARAMETERS_PATH.read_text(encoding='utf-8'))
            params['policy']['entry_score_min'] = 59
            param_path = tmp / 'params.json'
            param_path.write_text(json.dumps(params), encoding='utf-8')
            result = mod.review_package(param_path, FACTORS_PATH)
            self.assertIn('PARAMETER_CONTRACT_INVALID', result['blockers'])


if __name__ == '__main__':
    unittest.main()
