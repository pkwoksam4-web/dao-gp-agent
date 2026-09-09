from __future__ import annotations

import hashlib
import math

from audit_evidence_v1 import validate_artifact_digest, validate_sha256


EXPECTED_PITST_BASELINE = {
    'observed_transition_symbol_n': 233,
    'observed_transition_n': 386,
    'independent_symbol_n': 3,
    'independent_transition_n': 6,
}


def symbol_set_sha256(symbols: list[str]) -> str:
    normalized = sorted(str(x).strip().upper() for x in symbols)
    payload = ('\n'.join(normalized) + '\n').encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _add(errors: list[str], value: str) -> None:
    if value not in errors:
        errors.append(value)


def validate_fixed_probe_registry(doc: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ['FIXED_PROBE_REGISTRY_NOT_OBJECT']
    if doc.get('artifact') != 'FIXED_PROBE_REGISTRY_V1' or doc.get('version') != 'V1':
        _add(errors, 'FIXED_PROBE_REGISTRY_IDENTITY_INVALID')
    if doc.get('bare_label_forbidden') is not True:
        _add(errors, 'BARE_FIXED5_POLICY_NOT_ENFORCED')

    probes = doc.get('probes')
    if not isinstance(probes, list):
        return errors + ['FIXED_PROBE_LIST_INVALID']
    seen: set[str] = set()
    for probe in probes:
        if not isinstance(probe, dict):
            _add(errors, 'FIXED_PROBE_NOT_OBJECT')
            continue
        pid = str(probe.get('probe_id') or '').strip()
        if not pid:
            _add(errors, 'FIXED_PROBE_ID_MISSING')
            continue
        if pid in seen:
            _add(errors, f'DUPLICATE_PROBE_ID:{pid}')
        seen.add(pid)
        if pid.lower() == 'fixed5' or pid.upper() == 'FIXED5':
            _add(errors, f'BARE_FIXED5_LABEL_FORBIDDEN:{pid}')

        symbols = probe.get('ordered_symbols')
        if not isinstance(symbols, list) or not symbols:
            _add(errors, f'SYMBOL_SET_INVALID:{pid}')
            continue
        normalized = [str(x).strip().upper() for x in symbols]
        if len(normalized) != len(set(normalized)):
            _add(errors, f'DUPLICATE_SYMBOL_IN_PROBE:{pid}')
        expected_hash = symbol_set_sha256(normalized)
        if probe.get('sorted_symbol_sha256') != expected_hash:
            _add(errors, f'SYMBOL_SET_HASH_MISMATCH:{pid}')

        kind = probe.get('probe_kind')
        if kind == 'EXACT_FIXED_SET':
            if 'FIXED5' not in pid.upper():
                _add(errors, f'EXACT_FIXED_SET_ID_NOT_NAMESPACED:{pid}')
            if probe.get('contract_status') != 'VERIFIED_EXACT_FIXED_SET':
                _add(errors, f'EXACT_FIXED_SET_NOT_VERIFIED:{pid}')
            required = ('source_branch','source_run_id','source_artifact_id','source_artifact_digest')
            for key in required:
                if not probe.get(key):
                    _add(errors, f'EXACT_FIXED_SET_PROVENANCE_MISSING:{pid}:{key}')
            if probe.get('source_artifact_digest') and not validate_artifact_digest(probe.get('source_artifact_digest')):
                _add(errors, f'EXACT_FIXED_SET_ARTIFACT_DIGEST_INVALID:{pid}')
        elif kind == 'SEMANTIC_PILOT':
            if probe.get('contract_status') == 'VERIFIED_EXACT_FIXED_SET':
                _add(errors, f'SEMANTIC_PILOT_FALSE_FIXED_SET:{pid}')
            if probe.get('promotion_eligible') is not False:
                _add(errors, f'SEMANTIC_PILOT_MUST_NOT_PROMOTE:{pid}')
        else:
            _add(errors, f'UNKNOWN_PROBE_KIND:{pid}')

        if probe.get('promotion_eligible') is True and kind != 'EXACT_FIXED_SET':
            _add(errors, f'NONEXACT_PROBE_PROMOTION_FORBIDDEN:{pid}')

    assertions = doc.get('unverified_prior_assertions')
    if not isinstance(assertions, list):
        _add(errors, 'UNVERIFIED_ASSERTION_LIST_MISSING')
    else:
        for item in assertions:
            if not isinstance(item, dict):
                _add(errors, 'UNVERIFIED_ASSERTION_NOT_OBJECT')
                continue
            if item.get('status') != 'UNVERIFIED_PRIOR_ASSERTION_NOT_FREEZE_ELIGIBLE':
                _add(errors, 'UNVERIFIED_ASSERTION_STATUS_INVALID')
            if item.get('promotion_eligible') is not False:
                _add(errors, 'UNVERIFIED_ASSERTION_PROMOTION_FORBIDDEN')
    return errors


def validate_pitst_coverage(doc: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ['PITST_COVERAGE_NOT_OBJECT']
    if doc.get('artifact') != 'PIT_ST_EVIDENCE_COVERAGE_V1' or doc.get('version') != 'V1':
        _add(errors, 'PITST_COVERAGE_IDENTITY_INVALID')
    if doc.get('label') != 'INDEPENDENT_SAMPLE_CROSSCHECK':
        _add(errors, 'PITST_SAMPLE_LABEL_REQUIRED')

    values = {}
    for key in EXPECTED_PITST_BASELINE:
        try:
            values[key] = int(doc.get(key))
        except (TypeError, ValueError):
            values[key] = -1
            _add(errors, f'PITST_COUNT_INVALID:{key}')
    if values.get('independent_transition_n', -1) > values.get('observed_transition_n', -1):
        _add(errors, 'PITST_INDEPENDENT_TRANSITIONS_EXCEED_OBSERVED')
    if values.get('independent_symbol_n', -1) > values.get('observed_transition_symbol_n', -1):
        _add(errors, 'PITST_INDEPENDENT_SYMBOLS_EXCEED_OBSERVED')

    for key, expected in EXPECTED_PITST_BASELINE.items():
        if values.get(key) != expected:
            _add(errors, f'PITST_BASELINE_DRIFT:{key}')

    samples = doc.get('sample_transition_ids')
    if not isinstance(samples, list):
        _add(errors, 'PITST_SAMPLE_IDS_INVALID')
    else:
        if len(samples) != values.get('independent_transition_n'):
            _add(errors, 'PITST_SAMPLE_ID_COUNT_MISMATCH')
        if len(samples) != len(set(str(x) for x in samples)):
            _add(errors, 'PITST_SAMPLE_IDS_DUPLICATE')

    full_claim = doc.get('independent_full_transition_audit_pass') is True
    is_full = (
        values.get('independent_transition_n') == values.get('observed_transition_n') and
        values.get('independent_symbol_n') == values.get('observed_transition_symbol_n')
    )
    if full_claim and not is_full:
        _add(errors, 'FALSE_FULL_INDEPENDENT_AUDIT_CLAIM')

    if 'transition_coverage_pct' in doc and values.get('observed_transition_n', 0) > 0:
        expected = 100.0 * values['independent_transition_n'] / values['observed_transition_n']
        try:
            actual = float(doc['transition_coverage_pct'])
        except (TypeError, ValueError):
            actual = float('nan')
        if not math.isfinite(actual) or abs(actual - expected) > 1e-10:
            _add(errors, 'PITST_TRANSITION_COVERAGE_PCT_MISMATCH')
    if 'symbol_coverage_pct' in doc and values.get('observed_transition_symbol_n', 0) > 0:
        expected = 100.0 * values['independent_symbol_n'] / values['observed_transition_symbol_n']
        try:
            actual = float(doc['symbol_coverage_pct'])
        except (TypeError, ValueError):
            actual = float('nan')
        if not math.isfinite(actual) or abs(actual - expected) > 1e-10:
            _add(errors, 'PITST_SYMBOL_COVERAGE_PCT_MISMATCH')
    return errors
