# PORTFOLIO HARD RISK GUARD V1

Status: P0_GOVERNANCE_FROZEN / NUMERIC_MANDATE_REQUIRED
Production use: PROHIBITED UNTIL NUMERIC MANDATE IS FROZEN
Applies above: every model / regime / theme / stock / timing / execution layer
Supersedes for priority and governance: `PORTFOLIO_HARD_RISK_GUARD_V0.md`

## 1. Purpose

The portfolio hard-risk guard is the first production gate, not the last research refinement.

It protects the portfolio when the state machine, theme logic, stock ranking, event classification or execution assumptions are wrong.

No model-generated state may override this guard.

## 2. Priority

Production decision order is frozen as:

`HARD RISK GUARD -> DATA / EXECUTION ELIGIBILITY -> MODEL VETO / ROUTER -> SOFT EVIDENCE / RANKING -> POSITION TARGET -> EXECUTION`

A model may recommend less risk than the hard guard permits. It may never recommend more.

A favorable `NORMAL_RISK_ON`, `REPAIR`, strong relative strength, confirmed theme, or strong catalyst does not raise a hard limit.

## 3. Numeric mandate families

A single explicit portfolio-risk mandate must freeze numeric values for at least:

1. maximum single-name exposure;
2. maximum single-theme / industry exposure;
3. maximum factor-cluster / correlation concentration;
4. gross exposure ceiling;
5. net directional exposure ceiling;
6. benchmark beta ceiling;
7. liquidity / ADV / participation concentration ceiling;
8. overnight / gap-risk sizing rule;
9. daily portfolio-loss escalation threshold(s);
10. portfolio drawdown restriction threshold(s);
11. kill-switch threshold and recovery rule;
12. unavailable-data exposure ceiling;
13. maximum intended exposure when an exit could be blocked by T+1 / suspension / limit-down conditions.

Numeric values remain `NOT_FROZEN` until an explicit portfolio mandate is supplied. They must not be reverse-engineered from consumed historical performance.

## 4. Model-independent states

The hard-risk state machine is independent of market-regime labels:

- `HARD_RISK_NORMAL`
- `HARD_RISK_RESTRICTED`
- `HARD_RISK_NO_NEW_RISK`
- `HARD_RISK_DELEVERAGING`
- `HARD_RISK_KILL_SWITCH`

Transitions must be driven by portfolio exposure / loss / liquidity conditions under the frozen mandate, not by narrative market interpretation.

A model-generated `REPAIR` signal cannot reset a hard-risk state.

## 5. Pre-trade risk before post-trade exit

A-share execution constraints make post-signal exits unreliable as the only protection.

Before opening or increasing a position, sizing must account for the possibility that the intended exit is temporarily impossible because of:

- T+1 sell ineligibility;
- suspension;
- limit-down with no executable sell liquidity;
- severe gap-down;
- liquidity collapse / participation constraint.

Therefore the hard-risk guard must cap exposure ex ante so that an unavailable exit cannot create an unbounded portfolio-risk assumption.

No backtest may assume that a logical invalidation immediately becomes a fill.

## 6. Blocked deleveraging semantics

When the hard-risk policy requires reduction but execution is blocked:

- preserve the required target reduction;
- execute only eligible quantity;
- mark residual exposure as an unresolved hard-risk breach;
- prohibit new risk that would worsen the same breach;
- do not mark the issue resolved because an order could not be filled.

## 7. Theme / factor concentration

Different stock stories may represent the same portfolio risk.

The final mandate must control concentration using at least:

- industry / theme taxonomy;
- benchmark beta;
- explicit common-catalyst clusters;
- rolling dependence / correlation or another preregistered dependence measure;
- style-factor exposure where reliable data exist.

`Independent relative strength` is not equivalent to independent portfolio risk.

## 8. Rare-event interaction

Shock / transmission / active-de-risking modules may tighten risk beneath the hard ceiling.

By default they may not:

- increase leverage;
- raise gross/net exposure ceilings;
- relax single-name / theme limits;
- bypass execution or liquidity constraints.

A rare-event module that increases risk requires a separate prospective validation path and cannot inherit permission from a protective shock rule.

## 9. Evaluation fairness

Future model comparisons must report both:

- informational performance before application of the identical hard-risk guard; and
- executable / decision performance after application of the identical hard-risk guard.

The same hard limits, execution feasibility, cost assumptions and recovery policy must apply to the complex model and all baselines.

## 10. Link to minimum-effect design

The hard-risk mandate and the model action map must be frozen before `minimum_effect_delta_tau` can be economically justified.

Reason:

A rank-correlation improvement has no economic interpretation until the project defines what action a risk score changes and how much exposure / turnover / downside it changes.

The minimum meaningful effect must therefore be derived ex ante from decision utility and costs, not from the observed complex-model delta.

## 11. Numeric freeze rule

Numeric hard limits are a portfolio mandate, not a research discovery.

They must be set from explicit risk tolerance / capital / liquidity constraints or an independently justified mandate. They must not be optimized on consumed strategy outcomes.

One consolidated mandate may define all numeric fields. Until then:

`HARD_RISK_NUMERIC_FREEZE = BLOCKED_PORTFOLIO_MANDATE_REQUIRED`

This blocker does not prevent research-only informational tests, but it blocks production sizing, production PnL claims and production promotion.

## 12. Current status

Governance order and required fields are frozen in V1.

Numeric limits remain intentionally unfrozen. No arbitrary single-name, theme, beta, loss or drawdown number has been inserted.
