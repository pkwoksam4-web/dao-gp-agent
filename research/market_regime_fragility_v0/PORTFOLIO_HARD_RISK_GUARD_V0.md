# PORTFOLIO HARD RISK GUARD V0

Status: GOVERNANCE_PREREG
Production use: PROHIBITED
Numeric limits: NOT_FROZEN
Purpose: define model-independent portfolio safeguards that cannot be overridden by regime / theme / stock signals

## 1. Principle

The state machine is not the final line of defense.

A production portfolio requires hard limits that operate independently of whether the model currently believes the market is safe or risky.

No lower research layer may override this guard.

## 2. Required hard-limit families

Before any production promotion, the portfolio policy must freeze numeric values for at least:

1. **single-name exposure limit**
2. **single-theme / industry exposure limit**
3. **gross exposure limit**
4. **net directional exposure limit**
5. **portfolio beta exposure limit** relative to the chosen benchmark(s)
6. **correlation / factor-cluster concentration limit**
7. **liquidity / capacity concentration limit**
8. **daily loss / drawdown escalation limits**
9. **maximum portfolio drawdown / kill-switch policy**
10. **unavailable-data exposure cap**

Current numeric values are intentionally not invented here.

## 3. Independence from model state

Hard limits remain binding under every state, including:

- `NORMAL_RISK_ON`
- `REPAIR`
- strong RS
- confirmed theme
- strong catalyst

A high evidence score cannot authorize a breach of a hard risk limit.

## 4. Factor / correlation concentration

Several stocks with different company stories may still represent the same underlying risk factor.

The future portfolio implementation must identify concentration using at least:

- industry / theme taxonomy;
- broad market beta;
- size / growth / value / volatility style exposure where available;
- rolling return correlation or another preregistered dependence measure;
- explicit common-catalyst clusters when economically obvious.

No assumption that `independent stock-specific RS` automatically implies independent portfolio risk is allowed.

## 5. Drawdown control states

The production implementation must distinguish model state from portfolio-loss state.

Required independent portfolio states:

- `HARD_RISK_NORMAL`
- `HARD_RISK_RESTRICTED`
- `HARD_RISK_NO_NEW_RISK`
- `HARD_RISK_DELEVERAGING`
- `HARD_RISK_KILL_SWITCH`

Numeric transition levels and recovery rules: `NOT_FROZEN`.

These states are driven by portfolio risk / loss limits, not by narrative market interpretation.

## 6. Interaction with execution constraints

A hard-risk instruction does not imply an impossible fill.

If deleveraging is required but a position is blocked by T+1, suspension or limit-down conditions:

- record the required target reduction;
- execute only eligible quantity;
- keep the residual breach visible;
- prohibit using the blocked status to mark the risk issue resolved.

## 7. Recovery from hard-risk restriction

A model-generated `REPAIR` signal cannot by itself restore full portfolio risk after a hard-risk breach.

Recovery requires the separately frozen hard-risk recovery policy.

This prevents the same model that contributed to a drawdown from immediately self-authorizing re-risking.

## 8. Comparison / evaluation requirement

Any future economic comparison between models must report results both:

- before hard-risk guard effects, for informational attribution; and
- after applying the identical hard-risk guard, for executable portfolio comparison.

This prevents one model from appearing better solely because it received looser risk limits.

## 9. Production blocker

Until numeric limits, benchmark beta definition, factor-concentration method, loss limits and recovery rules are frozen by an explicit portfolio mandate, this layer remains `UNIMPLEMENTED_POLICY_LAYER` and production promotion is prohibited.
