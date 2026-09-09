# GP12 Turnover Formal-Anchor PIT Amendment 3 Implementation Plan

> **Execution:** use `superpowers:executing-plans` and `superpowers:test-driven-development`. Implement task-by-task on `gp/gp12-turnover-formal-v1`. Do not enable 847-symbol production in this plan.

**Goal:** Replace the all-history cross-source completeness gate with a Formal-required-chain gate that proves one pre-Formal exact anchor plus an exact zero-mismatch state chain through `2026-04-17`, while retaining older mismatches only as diagnostics.

**Architecture:** Extend `gp12_share_known_at_v1.py` with Formal-anchor analysis. Keep strict Amendment-2 exact date/value matching. The live workflow calls the centralized Formal-anchor gate. Then run a deterministic small cross-board pilot. Turnover materialization continues to consume only PIT-known states and remains fail-closed.

**Spec:** `docs/superpowers/specs/2026-09-09-gp12-turnover-formal-anchor-pit-amendment-3-design.md`

## Global constraints

- Formal start: `2020-06-01`.
- Formal end: `2026-04-17`.
- No fuzzy date tolerance, row-order pairing, interpolation, value-only matching, current-capital fallback, or cross-vendor substitution.
- Pre-anchor mismatches are diagnostics only and cannot enter resolver state.
- Post-anchor mismatches block PIT.
- `model_freeze_allowed=false` and `oos_metrics_allowed=false` throughout.
- `MAIN_NET_FLOW_UNBOUND` and `ADJUSTED_CLOSE_PIT_UNVERIFIED` remain independent blockers.

---

## Task 1 — RED/GREEN: Formal-anchor analysis

**Files:**
- Modify `scripts/gp12_share_known_at_v1.py`
- Modify `scripts/test_gp12_share_known_at_v1.py`

### Step 1: add RED tests

Add tests covering:

1. pre-anchor mismatch does not block when a later exact anchor known before Formal start exists;
2. latest eligible matched state is selected as anchor;
3. no eligible anchor returns `SINA_FORMAL_ANCHOR_MISSING`;
4. exact missing state after anchor returns `SINA_FORMAL_CHAIN_MATCH_MISSING`;
5. exact amount mismatch after anchor returns `SINA_FORMAL_CHAIN_AMOUNT_MISMATCH`;
6. ambiguous post-anchor match returns `SINA_FORMAL_CHAIN_MATCH_AMBIGUOUS`;
7. output reports sorted deterministic pre-anchor mismatch dates and Formal-chain mismatch dates;
8. Formal resolver state contains only anchor + exact post-anchor states through Formal end.

Required test shape:

```python
def test_pre_anchor_mismatch_is_diagnostic_but_formal_chain_can_pass():
    share_rows = [
        share_row('2017-05-26', 28000000000.0),
        share_row('2018-12-31', 28103763900.0),
        share_row('2020-06-30', 28103763900.0),
    ]
    structure_rows = [
        structure_row('2018-12-31', '2019-03-26', '2810376.39', 2),
        structure_row('2020-06-30', '2020-07-03', '2810376.39', 2),
    ]
    result = mod.bind_formal_anchor_states(
        '600000.SH', share_rows, structure_rows, 'a'*64, 'b'*64)
    self.assertEqual(result['formal_anchor_change_date'], '2018-12-31')
    self.assertEqual(result['pre_anchor_mismatch_dates'], ['2017-05-26'])
    self.assertEqual(result['formal_chain_mismatch_n'], 0)
    self.assertTrue(result['pit_verified'])
```

### Step 2: confirm RED

Run all existing contracts. Expected: only new tests fail because `bind_formal_anchor_states`/Formal-chain semantics do not exist.

### Step 3: implement minimum GREEN

Add:

```python
def bind_formal_anchor_states(
    symbol: str,
    share_rows: list[dict],
    structure_rows: list[dict],
    share_raw_sha256: str,
    structure_raw_sha256: str,
    formal_start: str = '2020-06-01',
    formal_end: str = '2026-04-17',
) -> dict:
    ...
```

Reuse exact `_matches_display` semantics from Amendment 2. Do not relax date/value matching.

Implement separate diagnostics for pre-anchor and post-anchor misses. Select latest matched state satisfying `change_date <= formal_start` and `known_at <= formal_start`. Return resolver states consisting only of anchor plus exact post-anchor matched states through Formal end.

### Step 4: run GREEN

All contracts must PASS.

---

## Task 2 — RED/GREEN: centralized Formal-anchor probe gate

**Files:**
- Modify `scripts/gp12_share_known_at_v1.py`
- Modify `scripts/test_gp12_share_known_at_v1.py`
- Modify `.github/workflows/gp12-turnover-formal-v1.yml`

### Step 1: add RED tests

Add `formal_anchor_probe_gate(...)` tests:

- any structural blocker => `BLOCKED`;
- missing anchor => `BLOCKED`;
- any Formal-chain blocker => `BLOCKED`;
- `pit_verified=false` => `BLOCKED`;
- only valid anchor + zero Formal-chain mismatch + `pit_verified=true` => `FORMAL_ANCHOR_PIT_PASS`.

Add workflow integration test requiring the YAML to call `known_mod.formal_anchor_probe_gate(`.

### Step 2: confirm RED

Expected: helper/workflow integration tests fail, all prior tests remain green.

### Step 3: implement GREEN

The workflow must stop using all-history binding as terminal evidence. It may still compute all-history diagnostics, but gate from `bind_formal_anchor_states` output.

Probe JSON must add:

- `formal_anchor_change_date`
- `formal_anchor_announcement_date`
- `formal_anchor_known_at`
- `pre_anchor_mismatch_n`
- `pre_anchor_mismatch_dates`
- `formal_chain_mismatch_n`
- `formal_chain_mismatch_dates`

### Step 4: rerun live `600000.SH`

Required before Task 3:

- contracts PASS;
- both HTTP sources 200/parsed;
- valid anchor exists;
- `formal_chain_mismatch_n == 0`;
- delayed known-at test passes;
- `DATA_GATE=FORMAL_ANCHOR_PIT_PASS`.

If not, freeze the live evidence and debug; do not proceed to pilot.

---

## Task 3 — deterministic cross-board pilot

**Files:**
- Modify `.github/workflows/gp12-turnover-formal-v1.yml`
- Add tests only if a reusable pilot helper is introduced.

### Step 1: choose fixed pilot symbols before results

Use a deterministic fixed set from representative families. Do not choose replacements after observing failures. Minimum target: one Shanghai main-board, one Shenzhen main-board, one ChiNext, one STAR-market symbol, all from the frozen universe if available.

Record the exact pilot list in workflow/repository code before running.

### Step 2: run both Sina sources for each pilot symbol

For each symbol emit:

- source HTTP/fetch status;
- parsed row counts;
- source SHA256 values;
- anchor dates;
- pre-anchor mismatch count;
- Formal-chain mismatch count/dates;
- PIT status and blockers.

### Step 3: pilot gate

Overall pilot PASS requires every fixed symbol to have:

- valid anchor;
- zero post-anchor Formal mismatch;
- PIT verified;
- no future-known-at violation.

Any failure keeps `TURNOVER_RATIO_UNBOUND` and must not cause symbol replacement or matching relaxation.

### Step 4: archive evidence

Upload deterministic pilot JSON plus exact raw source bytes per symbol where artifact size permits; otherwise upload raw SHA/metadata with failure evidence and keep source-fetch artifacts partitioned.

---

## Task 4 — readiness decision only after pilot

Do **not** run 847 in this plan.

If pilot passes, produce a next-step recommendation/design for 847-symbol production. If pilot fails, classify failures by source unavailable / parser / missing anchor / post-anchor mismatch without weakening semantics.

Regardless of pilot outcome:

- `TURNOVER_RATIO_UNBOUND` remains until full 847 Formal turnover artifact passes;
- `MAIN_NET_FLOW_UNBOUND` remains;
- `ADJUSTED_CLOSE_PIT_UNVERIFIED` remains;
- F11 remains blocked;
- candidate remains UNAPPROVED;
- model freeze and OOS metrics remain closed.
