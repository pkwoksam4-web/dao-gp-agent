# DAO2 Control-Plane Checkpoint — 2026-10-16

`verified_at: 2026-10-16`

This checkpoint separates verified repository state from inference. CI/Guard success is supporting evidence only; data/model PASS requires the relevant provenance and checkpoint contract.

## 1. Executive judgment

The project has not violated its fail-closed discipline, but the historical-recovery objective previously lacked an explicit exit condition. That is corrected here.

The remaining blockers are not equivalent:

| Area | Nature of blocker | Current verified state | Narrow? |
|---|---|---|---|
| A — Main Net Flow | exact missing semantic values | 16 exact symbol-date keys unresolved | Yes |
| B — Market Package | historical final scorer identity | final normalization/clipping/combination/mapping unresolved; authoritative I/O pairs = 0 | No |
| C — Sector PIT | authoritative raw Series provenance/coverage | 301 raw sector-date rows unresolved; 298 have derived evidence only, 3 do not | Yes in key set, but not only 3 rows |
| D — Label/Status | branch-local verified checkpoint | PASS/FROZEN on module branch | Closed locally |
| PR #21 | prospective runtime contract | two merge blockers remain after review | Executable now |

## 2. Repository identities

- `main`: `30b2406ed89b2c972f6d113456472a78611737e3`
- PR #15 / A: `gp/dao2-a-main-net-flow@aa0fab1baf163850dd8365299372b6cc1a8a9891`, draft/open/unmerged
- PR #16 / B: `gp/dao2-b-market-package@ddeddd1332fa785744006b28bdc75cece59802fb`, draft/open/unmerged
- PR #17 / C: `gp/dao2-c-sector-pit@aa6afc749f57efaaaaa4a43c22a9a86cfb3ed2ae`, draft/open/unmerged
- PR #18 / D: `gp/dao2-d-label-status@2a7056ffd61885046e34dc1494bc668143d96793`, draft/open/unmerged
- PR #21: `fix/shadow-settlement-contract-gates-v1@2c5437c09269fccd223cccc9addb7a6454f95d73`, open/unmerged; review gate currently NOT READY TO MERGE

## 3. Executability-first priority

| Priority | Item | Can execute now? | Action / trigger |
|---|---|---:|---|
| P0 | PR #21 merge-gate fixes | Yes | Implement calendar-keyed feature lookback continuity + late outcome capture class; TDD; no merge before re-review |
| P0 | A 16-key D-status classification | Yes | Read exact `tradestatus/isST/lifecycle` semantics for the 16 keys without mutating D; flag evidence conflicts, do not auto-N/A |
| P1 | A supplemental stratified identity controls | Partly | After D classification, add residual-adjacent controls for any ST/resumption/limit/IPO special states; no tuning against unknown residual values |
| P1 | iFinD readability | Conditional | `IFIND_REFRESH_TOKEN_MISSING` is an authentication prerequisite, not a data result; act on a real account/token renewal signal |
| P1 | B authoritative scorer recovery | No new input now | Reopen only on new source/executable or uniquely identifying authoritative I/O |
| P1 | C authoritative raw export | No new input now | Reopen on Wind/iFinD/RQData/Founder/Tushare entitlement or genuinely new official raw carrier |
| P2 | E acceptance | No | Wait for verified A/B/C/D checkpoints |
| P3 | F model/OOS | No | Wait for E |

## 4. Module A — corrected evidence boundary

Frozen counts:
- formal expected = `1,011,607`
- resolved = `1,011,591`
- unresolved = `16`

The public carriers prove semantic identity only on their covered rows. They do not prove that the original/upstream Tushare source itself omitted the 16 residual keys.

Correct statement:
> The verified public carriers reproduce the required Tushare moneyflow semantics on covered samples but do not cover the 16 residual keys; therefore current evidence cannot determine whether the original upstream source contained those rows.

Repository evidence: `data/GP12_MAIN_NET_FLOW_SOURCE_OMISSION_EVIDENCE_V1.json` explicitly states that the course/public-snapshot omission cannot be distinguished from an upstream Tushare omission.

### A status/lifecycle audit rule

Use the frozen D semantics to classify each exact residual symbol-date. A moneyflow absence alone never implies N/A.

- If D confirms a valid/tradable symbol-date, keep the expected row and continue exact-value recovery.
- If D conflicts with the Formal RAW axis while Formal turnover is non-zero, classify `EXPECTED_AXIS_EVIDENCE_CONFLICT` and investigate the axis; do not silently change expected count.
- Only direct evidence that a key should not exist in the Formal expected domain can justify reducing `formal_expected_rows`.

### A identity controls

`data/dao2/modules/A_JESSICA_KNOWN_ROW_CONTROL_SCOPE_V1.json` contains 8 control rows across 2020–2023 and SH/SZ, selected on same/residual-adjacent dates with activity-magnitude diversity. Four required moneyflow amount fields per row produce `8 × 4 = 32` exact comparisons.

The 32/32 gate is necessary but not sufficient for every residual regime. The frozen scope does not by itself prove explicit ST/resumption/limit-up/down/IPO-first-day coverage. Add stratified residual-adjacent controls only after D classification identifies which special regimes are actually relevant.

### iFinD

`data/dao2/modules/A_IFIND_DIRECT_RUNTIME_20261010.json` records `IFIND_REFRESH_TOKEN_MISSING`, `history_request_executed=false` and classification `AUTHENTICATION_PREREQUISITE_MISSING_NOT_IDENTITY_FAILURE`. Do not describe this route as a negative data result.

## 5. Module B — historical scorer exit condition

B remains structurally underdetermined rather than a small missing-data gap:
- benchmark = PASS_SUBCOMPONENT
- raw breadth executable identity = PASS_SUBCOMPONENT
- authoritative final-scorer I/O pairs = `0`
- historical final scorer source/executable = not recovered
- normalization, clipping, combination and final mapping = not historically bound

`recovery_decision_date: 2026-10-30` (proposed for owner confirmation on 2026-10-23; 10/31 falls on Saturday)

If no new authoritative carrier exists by that date, historical final-scorer recovery stops being an open-ended active loop. `MARKET_BREADTH_UNBOUND` remains formally unresolved/frozen and execution switches to a separately versioned successor reconstruction contract explicitly labelled **NOT the historical GP12 scorer**. The historical recovery path remains preserved for future authoritative evidence.

## 6. Module C — provenance decision

Counts remain internally consistent:
`43,084 - 42,783 = 301 = 298 + 3`.

Branch-local recorded disposition (not owner-confirmed):
`DERIVED_CLOSE_PROVENANCE_MIGRATION = REJECTED_FOR_HISTORICAL_IDENTITY_PATH`.

Owner confirmation: `PENDING`. The branch status does not establish the owner's final decision.

The 298 derived-close rows remain evidence-only and may not close historical Series identity. Thus historical C is missing 301 authoritative raw keys, not only three rows.

The 2026-10-16 official SWS re-check produced a false positive in an intermediate interpretation: OHLC rows from `2001-08-06`, `2001-10-08`, `2001-10-22` were mistaken for the target 2021 dates. The frozen exact probe still finds the three true 2021 target dates absent. No rows were admitted and no checkpoint was advanced.

## 7. Module D — data-layer PASS basis

D is PASS/FROZEN **on its module branch**, not on main.

Identity:
- branch commit: `2a7056ffd61885046e34dc1494bc668143d96793`
- checkpoint: `artifact/D_LABEL_STATUS_CHECKPOINT_V1.json`
- checkpoint Git blob SHA: `9cf8d607156823d460373f058207b98e1e4aa51e`
- PR #18: draft/open/unmerged

Data-layer evidence:
- lifecycle = `847/847`
- Formal calendar = `1,426/1,426`
- required-date gaps = `0`
- transition cross-check = `6/6 PASS`
- Formal overlay rows = `1,021,953`
- V4.82 tradestatus corrections = `4`, with `isST` unchanged
- source artifact = `gp-pit-st-v480-final-audit`
- source artifact ZIP SHA256 = `a86d807829deb393e012e93fea44637cefd1759c973fa109e2a728647fa83f58`

Contract tests and Guard SUCCESS are supporting consistency checks; they are not the data-PASS basis.

## 8. PR #21 — merge-gate policy

Current maturity-date correction is retained: 5D/20D target dates come from the frozen exchange calendar and may never shift to later available rows.

Two blockers remain before merge:

### 8.1 Outcome availability vs input PIT

Prediction inputs and Shadow observation must be prospective LIVE_PIT. The realized outcome is an ex-post fact. If the exact target-day live collector missed a bar, an otherwise valid cohort should not be permanently destroyed solely for that reason.

Required late-capture class:
`SETTLEMENT_LATE_CAPTURED`

Conditions:
- forecast/observation immutable before maturity;
- exact target date only;
- authoritative provider;
- frozen close/adjustment convention;
- provider/provenance + retrieval timestamp + immutable hash;
- pure LIVE target settlements and late-captured settlements reported separately;
- no later-date substitution.

### 8.2 Feature lookback continuity

The 2026-09-30 incident was caused by rolling features using the last N existing DB rows. The current `prev_close` gate does not prove that every required exchange-calendar session inside the whole N-day lookback exists.

Before merge, feature windows must be bound to exchange-calendar keys and fail closed on both:
- missing expected immediate predecessor;
- missing interior lookback session.

PR #21 review gate is recorded in review `5545478529`. CI PASS at current HEAD does not override this review decision.

## 9. Glossary

- **Jessica controls** — control rows pinned from `Jessica-Zhangyj/dlquant@6b245fa09cb628f3bcb812f0662bfef520e65fb4`, used to test exact Tushare moneyflow field identity before any residual values are admitted.
- **Tushare/Jessica semantics** — the exact `moneyflow` large/extra-large active buy/sell fields and unit convention used by the pinned course carrier; not a generic “main flow” proxy.
- **Moonlit-Pages carrier** — `Moonlit-Pages/cozeclaw-workspace@526ebbb94066bc623add892f6f8c21378d3e945a`, a public carrier that exactly reproduces a covered Tushare moneyflow snapshot but has no residual coverage.
- **Jiu-7131 carrier** — `Jiu-7131/BigDataVisualization@102c67acda5151545d54444199140bd869c49004`, a public raw Tushare moneyflow directory used for independent schema/field identity checks.
- **PASS_SUBCOMPONENT** — a component identity has been verified, but the owning module is not fully PASS.
- **Historical identity path** — only evidence classes that prove the historical data/scorer contract may close blockers. Derived/candidate behavior can support diagnostics or a successor model but cannot be relabelled as recovered history.

## 10. Governing conclusion

There is no evidence of a discipline breach in the fail-closed rules. The material weakness was the absence of explicit exit conditions and several over-strong evidence interpretations. Those are corrected in this checkpoint: A source omission is no longer inferred, B now has a decision date, C derived provenance is explicitly rejected for historical identity, D PASS is tied to data-layer evidence and branch identity, and PR #21 is blocked from merge pending the two runtime contract fixes above.


## 11. Governance status update — 2026-10-22

- The proposed B decision date is 2026-10-30, subject to owner review on 10/23; this corrects the prior Saturday date.
- C's branch-local historical identity migration rejection remains recorded as branch state only. The owner has not confirmed it; do not treat the rejection as a final project decision.
- Main controller naming is 主控 Agent 3, per the owner's prior explicit instruction.
