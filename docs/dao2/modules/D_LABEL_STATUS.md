# Module D — LABEL_STATUS

Status: **VERIFYING**

## Objective

Close `LABEL_PROVENANCE_UNBOUND` and `STATUS_SEMANTICS_INCOMPLETE` without changing A/B/C/E/F state, inventing a new historical label, or converting execution diagnostics into fill mechanics.

## Status audit correction

The course-repository `stock_st` set is **supplementary evidence only**. Its 12 missing Formal dates are not a V4.80 PIT-ST production gap.

The formal V4.80 PIT-ST audit remains the base:

- lifecycle: 847/847 PASS
- calendar: 1426/1426 exact
- missing required dates: 0
- duplicate daily keys: 0
- invalid daily rows: 0
- outside-calendar rows: 0
- CNINFO transition cross-check: 6/6 PASS
- formal overlay rows: 1,021,953
- artifact: `gp-pit-st-v480-final-audit` / ID `9972698555`
- digest: `sha256:a86d807829deb393e012e93fea44637cefd1759c973fa109e2a728647fa83f58`

V4.82 contributes exactly four `tradestatus` point corrections on 2024-06-13: 002087.SZ, 600647.SH, 600766.SH and 603133.SH. They do not change `isST`.

## Exact GP12 candidate status contract

The candidate snapshot requires exactly `known_at + is_st + tradable + upper_limit`.

- **is_st**: V4.80 PIT-ST `isST == 1`; unknown/missing fails closed.
- **tradable**: corrected PIT-ST `tradestatus == 1`; it represents suspension/trading status only and does not absorb ST or price-limit state.
- **upper_limit**: on a tradable signal date, same-date raw daily close equals the official Tushare `stk_limit.up_limit`. It is a **closed-at-upper-limit** state, not an intraday touch and not a fill claim.
- **status eligibility**: `(not is_st) and tradable and (not upper_limit)`.
- **PIT timestamp**: this after-close status package is available no earlier than 15:00 Asia/Shanghai and must satisfy `known_at <= as_of`.
- **future horizon**: T+1/T+2/T+3 future suspension/limit/delist states are outcome/diagnostic fields only. They cannot enter the T signal, cannot shift the label date to the next stock bar, and do not define actual fills.

For `upper_limit`, the pinned course repository supplies only candidate source/semantic provenance, not historical GP source identity: commit `6b245fa09cb628f3bcb812f0662bfef520e65fb4` downloads Tushare `stk_limit` for every SSE-open date. Its pinned calendar has 2,516 open dates for 2016-01-04..2026-05-18, the manifest records 2,516 limit files, and the Formal subwindow contains 1,426 open dates. The raw limit rows are not committed in that public repository, so this evidence binds source semantics and date-level collection provenance rather than pretending immutable row bytes exist in this branch.

## Historical label provenance

Historical GP V1.1 Daily Base labels are bound to recovered `v11_offline_backtest_v3_10.zip`:

- archive SHA256: `d526b1341694e14b13ee753200165c0701c3948f984a2e96211bb812f856f03d`
- `src/run_backtest.py`: `6b81feaa37ade4970fcda62601e2a699951fe00ef678ee83fa84f84928d69ff1`
- `src/run_panel_backtest.py`: `62229450e488a75ba4352a239fc762a2b9f48034f765966242632970937278c2`
- `src/run_formal_pipeline.py`: `dde897aa7daeca318ab438cd985d7708a5db7b7bc89a7cb47ef231a4aad94c8c`

Recovered scope includes T+1/T+2/T+3, MFE/MAE, fixed-hit thresholds and ATR-adaptive three-day first-touch UP/DOWN/FLAT/AMBIG. The six panel targets are `up_close_1`, `up_close_2`, `up_close_3`, `hit_up2_3d`, `hit_up4_3d`, `hit_dn2_3d`, with target-specific purge. Their clock advances by **market trading days**, not “next available stock K-line.”

The exact historical formulas remain authoritative in the byte-identified V3.10 source. Module D deliberately does not re-author missing formula text and does not substitute the course repository's newer label code.

## Boundary

This module closes provenance/semantics only. It does **not**:

- adopt `GP12_REBUILD_CANDIDATE_V1` as historical GP V1.1;
- recover the historical final entry/exit/fill policy;
- turn future execution diagnostics into actual fill mechanics;
- authorize Model Freeze or OOS;
- modify A/B/C/E/F module state.

Verification is performed by `scripts/dao2_label_status_contract_v1.py`, its unit tests, and the Module D guard workflow. PASS is written only after a verified checkpoint exists.
