# MODULE DOWNGRADE / CHANGE CONTROL V1

Status: GOVERNANCE_FROZEN
Version: `MODULE_DOWNGRADE_CHANGE_CONTROL_V1`
Production change: NONE
Applies to: all decision-active research / shadow / candidate / production-frozen modules in this architecture

## 1. Separate three concepts

Do not collapse:

1. **Evidence grade** — `E0..E4`, describing empirical support.
2. **Module lifecycle** — `CONCEPTUAL / RESEARCH_ONLY / SHADOW_ONLY / CANDIDATE / PRODUCTION_FROZEN / REJECTED_FOR_PROMOTION`.
3. **Runtime deployment state** — whether a deployed version is currently allowed to affect decisions.

Runtime deployment state is:

- `ENABLED`
- `SHADOW`
- `OFF`
- `QUARANTINED`

A production-frozen module may be `OFF` without pretending its old evidence disappeared. Conversely, strong historical evidence never permits an invalid or drifted implementation to remain `ENABLED`.

## 2. Fail-closed precedence

Runtime control precedence is:

`QUARANTINED > OFF > SHADOW > ENABLED`

A lower-precedence positive state cannot override a higher-precedence integrity/safety restriction.

`QUARANTINED` means the module/version is not trusted for decision use until the breach is adjudicated.

`OFF` means the version is intentionally disabled but not necessarily invalidated.

`SHADOW` means outputs may be computed/logged but cannot change production action or exposure.

## 3. Immediate integrity downgrade triggers

The following require immediate `QUARANTINED` for the affected module/version, independent of performance:

- confirmed look-ahead, survivorship or decision-timestamp contamination;
- required PIT evidence cannot be reproduced from the bound carrier and no byte-/semantic-equivalent source has been admitted;
- rule/config/code hash differs from the frozen identity without an approved version change;
- implementation parity failure between the frozen contract and the deployed calculation;
- provenance/hash mismatch on a required immutable input;
- required input semantics are discovered to differ from the semantics assumed by the frozen contract;
- a supposedly unavailable/missing input is silently imputed as NORMAL/zero/healthy contrary to fail-closed rules;
- an execution rule assumes fills that are prohibited by the bound market/tradability contract;
- a manual override or online-learning path mutates a frozen rule/output without being separately versioned and logged.

These are integrity events, not predictive-performance events. No numeric threshold is needed to activate them.

## 4. Immediate safety downgrade triggers

If a production-active module depends on a required hard-risk/execution safeguard and that safeguard becomes unavailable or fails validation:

- the affected action path must not remain `ENABLED`;
- default state is `OFF` or stricter according to the independent hard-risk system;
- switching to `SHADOW` is allowed only if shadow computation itself is safe and cannot affect production exposure.

A favorable model score/state never bypasses a hard-risk or execution failure.

## 5. Predictive/economic deterioration downgrade

No generic numeric performance threshold is invented in this governance document.

Before any module becomes `PRODUCTION_FROZEN`, its production contract must preregister:

- monitored primary metric(s);
- monitoring horizon / effective sampling unit;
- uncertainty method;
- false-alarm / tail-risk / turnover metrics relevant to its purpose;
- exact downgrade boundary;
- minimum evidence needed to trigger the boundary;
- target runtime state after breach (`SHADOW` or `OFF`);
- recovery/re-enable criteria.

Until those module-specific boundaries are frozen **before** monitoring outcomes are observed, performance-based automatic downgrade is `NOT_FROZEN` and cannot be improvised from realized PnL.

Rare-event modules must use independent event episodes rather than daily row count.

## 6. Data degradation

Single-decision missing/unavailable data is handled by the module's fail-closed semantics and does not automatically rewrite its lifecycle.

Persistent feed degradation may move a deployment to `SHADOW` or `OFF` only under a preregistered data-availability rule. Numeric persistence/coverage thresholds remain module-specific and must be frozen before use.

An unplanned source outage may always trigger a conservative `OFF` if continuing would require unsupported imputation or stale inputs.

## 7. Authority to change frozen items

Agents may:

- detect drift/breaches;
- prepare evidence;
- draft a new version;
- add tests;
- recommend a downgrade;
- automatically apply fail-closed runtime restrictions already authorized by a frozen safety contract.

Agents may **not** self-approve a production frozen-rule change.

Changing any frozen production rule, threshold, state semantics, precedence, source contract, execution assumption or hard-risk numeric mandate requires explicit approval from the designated human production owner / authorized maintainer for that release.

The approver identity is deployment metadata, not a model feature.

Emergency safety action is asymmetric: disabling/quarantining a suspect path may be automatic; re-enabling a changed production path requires the normal approval/evidence process.

## 8. Change classes

### Class A — evidence/documentation only

No executable semantic change. Examples: adding a missing source citation or recording an expired artifact.

May keep the same executable version if hashes/semantics are unchanged.

### Class B — implementation repair with unchanged frozen semantics

Requires:

- regression test that fails before the repair and passes after;
- proof that intended rule semantics are unchanged;
- new implementation hash/build identity;
- parity verification against the frozen contract.

Runtime may remain/return `SHADOW` until parity is verified. Production re-enable still follows deployment approval.

### Class C — rule/data-contract/state-space change

Examples:

- threshold change;
- input field/source semantic change;
- state add/split/merge;
- precedence/veto change;
- execution/fill rule change;
- risk-score/action-map change.

Requires a new module/contract version. If motivated by observed evaluation outcomes, the revised hypothesis resets to at most `E1` under `MODULE_PROMOTION_GOVERNANCE_V1` and must use a new genuinely unused evaluation window before formal promotion.

### Class D — hard-risk mandate change

Requires explicit human risk-owner approval. Numeric limits are governance constraints, not optimization parameters, and cannot be tuned on consumed strategy outcomes.

## 9. Cooling rule

No arbitrary calendar duration is invented here.

For Class C/D changes, the **evidence cooldown** is mandatory:

- the outcome window that motivated or informed the change is sealed/consumed;
- the changed version cannot use that same window for formal promotion evidence;
- definitions, hashes, primary endpoint and baseline must be locked before the next genuinely unused evaluation window opens;
- re-enable/promotion requires the evidence level mandated by the destination lifecycle.

A numeric minimum wall-clock/trading-day cooldown remains `NOT_FROZEN` unless the production owner explicitly mandates one. The absence of a numeric duration never permits same-window post-hoc validation.

Emergency integrity fixes may be deployed only to remove unsafe behavior; they do not earn performance evidence from the incident that caused the fix.

## 10. Online learning prohibition

`SHADOW / LEARNING` is an observation/research layer, not an autonomous production-parameter update loop.

It may:

- collect prospective outcomes;
- calculate preregistered diagnostics;
- identify candidate failure modes;
- propose new versions.

It may not silently modify:

- frozen thresholds;
- state boundaries;
- feature weights;
- source precedence;
- action maps;
- risk limits;
- production code/config hashes.

Any learned change is a new version and follows change control.

## 11. Re-enable conditions

A `QUARANTINED` module cannot return directly to `ENABLED` merely because the immediate symptom disappeared.

Minimum governance path:

1. root cause identified and evidenced;
2. affected scope/rows/windows identified;
3. fix or source restoration versioned;
4. contract/regression tests pass;
5. integrity/parity reverified;
6. any invalid formal claims withdrawn/recomputed;
7. required human approval obtained for production re-enable.

If the fix changes model semantics, use Class C rules and new unused evidence; do not call it a simple repair.

## 12. Manual overrides

Manual intervention never rewrites the model's original output.

Every production/shadow override must be written to `MANUAL_OVERRIDE_LEDGER_V1` before the action cutoff where operationally possible, including the model's original conclusion, the replacement action, reason, actor role and evidence references.

Model-only evaluation and as-operated/human-assisted evaluation must remain separable.

## 13. Current status

This governance freezes categorical downgrade/change-control semantics only.

Not frozen here:

- module-specific predictive deterioration thresholds;
- numeric data-availability thresholds;
- numeric wall-clock/trading-day cooldown;
- portfolio hard-risk numbers.

Those must not be invented from consumed outcomes.
