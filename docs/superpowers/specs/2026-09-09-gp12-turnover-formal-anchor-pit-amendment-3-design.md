# GP12 Turnover Formal V1 — Amendment 3: Formal-Anchor PIT

Status: approved design amendment. This document narrows Amendment 2's historical cross-source binding requirement to the exact evidence actually required for the frozen Formal window `2020-06-01 .. 2026-04-17`.

## Problem discovered by live evidence

For `600000.SH`, the live ShareAmount and StockStructure sources each parse to 73 historical states, but exact same-date/value binding yields only 63 states. The 10 unmatched ShareAmount dates are historical legacy mismatches before the Formal window:

- 2002-08-23
- 2008-04-25
- 2009-06-10
- 2009-09-29
- 2010-06-11
- 2011-06-07
- 2014-12-18
- 2015-03-26
- 2016-06-24
- 2017-05-26

The latest exact dual-source state known before the Formal start is `change_date=2018-12-31`, `announcement_date=2019-03-26`, therefore `known_at=2019-03-26`.

Requiring every pre-history state back to listing to cross-match would reject a usable Formal PIT chain for reasons that cannot affect any Formal date. Conversely, fuzzy date matching or row-order pairing would create unverifiable history and is prohibited.

## Formal-anchor rule

For each symbol, build exact dual-source candidate states using the Amendment-2 same-date and display-precision amount rules.

A **Formal anchor** is the exact matched state with the greatest `change_date` such that:

- `change_date <= 2020-06-01`
- `known_at <= 2020-06-01`

If no such state exists, add blocker `SINA_FORMAL_ANCHOR_MISSING` and keep PIT blocked.

## Required chain after the anchor

Let `anchor_change_date` be the selected Formal anchor.

Every ShareAmount state with:

`anchor_change_date < change_date <= 2026-04-17`

must have exactly one StockStructure match under Amendment 2's strict same-date and display-precision amount rule.

Any missing, ambiguous, or amount-mismatched state after the anchor is a Formal-chain blocker and must keep PIT blocked.

No nearest-date tolerance, row-order pairing, value-only pairing, interpolation, present-day fallback, or cross-vendor substitution is permitted.

## Pre-anchor mismatches

ShareAmount states earlier than the selected anchor may fail to match without blocking Formal PIT, provided all of the following are true:

1. they are strictly earlier than `anchor_change_date`;
2. they are recorded deterministically as provenance;
3. they are never included in the Formal state resolver;
4. they never alter the selected anchor;
5. they never alter any post-anchor match result.

Record:

- `pre_anchor_share_row_n`
- `pre_anchor_matched_state_n`
- `pre_anchor_mismatch_n`
- `pre_anchor_mismatch_dates`

These are historical diagnostics only and must not remove or create Formal rows.

## Formal-chain report

The binder must emit a deterministic report containing at least:

- `formal_start = 2020-06-01`
- `formal_end = 2026-04-17`
- `formal_anchor_change_date`
- `formal_anchor_announcement_date`
- `formal_anchor_known_at`
- `formal_anchor_outstanding_share_shares`
- `formal_required_share_row_n`
- `formal_matched_state_n`
- `formal_chain_mismatch_n`
- `formal_chain_mismatch_dates`
- `pre_anchor_mismatch_n`
- `pre_anchor_mismatch_dates`
- `pit_verified`
- sorted unique `blockers`

`pit_verified=true` requires:

- a valid Formal anchor;
- zero Formal-chain missing matches;
- zero Formal-chain ambiguous matches;
- zero Formal-chain amount mismatches;
- no future-known-at violation;
- exact valid source SHA identities.

## Resolver input

The Formal resolver may consume only:

- the selected Formal anchor; and
- exact matched states after the anchor through `2026-04-17`.

Pre-anchor historical states are excluded from resolver input even if matched.

For Formal trade date `d`, select the eligible state with latest `change_date` satisfying:

- `change_date <= d`
- `known_at <= d`

## 600000.SH acceptance gate

Before any multi-symbol pilot, the live `600000.SH` probe must prove:

- both sources HTTP-fetch successfully;
- both sources parse successfully;
- a valid Formal anchor exists;
- live anchor is recorded from source bytes, not hard-coded;
- all ShareAmount states after the anchor through `2026-04-17` cross-match exactly;
- `formal_chain_mismatch_n = 0`;
- pre-anchor mismatch dates are reported but do not block;
- a delayed announcement state is unavailable before `known_at` and available on/after `known_at`;
- `DATA_GATE=FORMAL_ANCHOR_PIT_PASS` only when all above hold.

Otherwise the probe must return `DATA_GATE=BLOCKED` while the workflow itself may remain operationally successful so evidence is retained.

## Multi-symbol pilot before 847

Do not jump directly from one symbol to 847.

After `600000.SH` passes, run a small deterministic pilot across representative exchange/board families from the frozen universe. The pilot must use fixed symbols selected before observing results and report per-symbol:

- fetch status for both sources;
- anchor identity;
- pre-anchor mismatch count;
- Formal-chain mismatch count;
- PIT status and blockers.

Any pilot symbol without a valid anchor or with a post-anchor mismatch remains blocked. Do not relax matching semantics based on pilot failures.

Only after the pilot passes may an 847-symbol production design be considered.

## Safety invariants

This amendment does not change:

- candidate factor formulas;
- F11 semantics;
- candidate adoption status;
- historical GP V1.1 recovery blockers;
- model-freeze policy;
- OOS policy.

Always retain:

- `candidate_adoption_status = UNAPPROVED` where applicable;
- `candidate_freeze_ready = false`;
- `model_freeze_allowed = false`;
- `oos_metrics_allowed = false`.

Even a successful turnover Formal chain only addresses `TURNOVER_RATIO_UNBOUND`. `MAIN_NET_FLOW_UNBOUND`, `ADJUSTED_CLOSE_PIT_UNVERIFIED`, and the F11 blocker remain until independently proven.
