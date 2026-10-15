# INTERNAL FRAGILITY V0 — PREREG FIELDS V1

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

## Objective

Evaluate whether an internal-fragility state can distinguish broad-market vulnerability from harmless index/breadth divergence without using future outcomes to define the state.

## Evidence fields to record at signal close

No field below has a frozen threshold. Each is categorical/descriptive for the current research stage.

1. **Cap-weighted index state**
   - Shanghai Composite / CSI300 / ChiNext / STAR50 direction and relative strength.

2. **Broad breadth state**
   - advancing vs declining stocks;
   - whether median-stock participation is materially weaker than headline indices.

3. **Small/mid-cap state**
   - CSI1000 / micro-cap relative strength versus cap-weighted indices.

4. **Leadership concentration**
   - whether gains are concentrated in a narrow set of large-cap leaders / themes;
   - whether the market can support multiple independent themes.

5. **Leadership continuation quality**
   - leaders strengthening, stalling, failing breakouts, or entering broad drawdown;
   - high-level momentum / limit-up continuation quality where contemporaneous public reports provide it.

6. **Theme breadth / dispersion**
   - whether a leading theme is broad-based or dominated by a few names;
   - whether top/median/bottom members move coherently.

7. **Turnover / liquidity state**
   - expanding vs contracting turnover;
   - active distribution versus low-liquidity drift.

8. **External / derivative stress**
   - contemporaneous external equity, rates, commodity, FX, futures/derivative stress when available;
   - absence of such evidence must remain absence, not inferred zero.

9. **Event / catalyst context**
   - whether the day is dominated by a known macro, geopolitical, policy, earnings, or industry event.

## Research state labels

- `NORMAL_RISK_ON`
- `NORMAL`
- `INTERNAL_FRAGILITY_WATCH`
- `INTERNAL_FRAGILITY_CONFIRMED`
- `EXTERNAL_SHOCK`
- `ACTIVE_DE_RISKING`
- `REPAIR`

These labels are research semantics only.

## Assignment principles

- Breadth weakness alone cannot produce `CONFIRMED`.
- Index strength alone cannot produce `NORMAL_RISK_ON` when breadth/leadership evidence conflicts.
- `CONFIRMED` requires multiple independent deterioration channels, especially leadership deterioration and/or small-cap stress in addition to breadth divergence.
- `EXTERNAL_SHOCK` can override a previously healthy local state, but does not itself specify an execution price or force an open liquidation.
- `REPAIR` requires improving price acceptance and breadth/leadership evidence; a one-day index rebound is insufficient by itself.

## Outcome protocol

For each newly tested signal date, record outcomes only after the above same-day fields and preliminary state have been written.

Primary outcome benchmark:
- CSI1000 close-to-close forward return from the signal close at +1D, +3D, +5D.

Secondary diagnostics when useful:
- ChiNext / STAR50 forward return;
- representative high-beta leadership basket;
- maximum adverse/favorable path during the evaluation horizon.

## Evaluation framing

Do not optimize for raw hit rate alone. Separate:

1. `TAIL_RISK_SAVE` — meaningful reduction of severe downside exposure;
2. `FALSE_ALARM_COST` — opportunity cost from unnecessary de-risking;
3. `MILD_WARNING` — limited downside / transient weakness where a full risk-off response would be excessive;
4. `REPAIR_CAPTURE` — ability to re-open risk after stress without waiting for full index recovery.

## Prohibited during this phase

- No threshold fitting on already consumed windows.
- No retrospective relabeling solely because forward returns were good/bad.
- No production-core weight changes.
- No MA threshold optimization.
- No use of these windows as future formal OOS.
