# RISK EVIDENCE SCORE MAPPING V1

Status: GOVERNANCE_PREREG
Production use: PROHIBITED
Purpose: evaluation normalization only

## 1. Scope

This mapping exists only so the complex research architecture and the simple baseline can be compared on the same ordinal scale.

It is **not**:

- a probability of decline;
- a position-sizing rule;
- a sell / buy rule;
- a layer-conflict or veto hierarchy;
- a substitute for A-share execution constraints.

## 2. Ordinal scale

- `0 = risk acceptance / risk-on evidence`
- `1 = normal / caution evidence`
- `2 = restricted-risk evidence`
- `3 = severe-risk / active-de-risking evidence`

Only ordering is implied. Distances between scores are not assumed equal.

## 3. Complex-model canonical state mapping

The resolved canonical market / fragility state maps exactly as follows:

| Canonical state | RISK_EVIDENCE_SCORE |
|---|---:|
| `NORMAL_RISK_ON` | 0 |
| `NORMAL` | 1 |
| `INTERNAL_FRAGILITY_WATCH` | 1 |
| `INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY` | 2 |
| `INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY` | 3 |
| `EXTERNAL_SHOCK` | 2 |
| `ACTIVE_DE_RISKING` | 3 |
| `REPAIR` | 1 |

If no canonical state can be resolved from PIT evidence at the decision timestamp, output `null / UNAVAILABLE`; do not coerce to `NORMAL`.

## 4. Important separation from source / transmission fields

`SHOCK_SOURCE_PERSISTENCE` and `LOCAL_TRANSMISSION_STATE` are **not independently added to the score in V1**.

Reason: adding ad-hoc score increments or floors here would silently create an unvalidated conflict-resolution policy before the layer-priority / veto contract is frozen.

Those fields may influence which canonical market state the native complex classifier resolves to, but that resolution logic must be preregistered separately before a formal unused comparison set is opened.

This prevents double-counting the same shock evidence through multiple layers.

## 5. Simple-baseline mapping

`BASELINE_1 = MOMENTUM_VOL_REGIME_V1`:

| Baseline state | RISK_EVIDENCE_SCORE |
|---|---:|
| `SIMPLE_RISK_ON` | 0 |
| `SIMPLE_NEUTRAL` | 1 |
| `SIMPLE_RISK_OFF` | 2 |
| `SIMPLE_UNAVAILABLE` | null |

`BASELINE_0 = NO_REGIME_OVERLAY` is a constant neutral bookkeeping reference score `1` when a scalar is required. This does not create a trading signal.

## 6. No probability language

The score must be called:

`RISK_EVIDENCE_SCORE`

It must not be renamed:

- probability;
- win rate;
- crash probability;
- downside probability;

unless a future version is explicitly probability-calibrated on an unused dataset.

## 7. Version-control rule

Once the first formal unused comparison window is opened, this V1 mapping cannot be changed for that evaluation.

If empirical results motivate a different mapping, create `RISK_EVIDENCE_SCORE_MAPPING_V2`, reset the revised hypothesis evidence grade as required by governance, and test it on a new unused window.
