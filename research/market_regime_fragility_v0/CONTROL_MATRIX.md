# INTERNAL FRAGILITY V0 — CONTROL MATRIX

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

## Outcome metric

For the control matrix, use CSI 1000 close-to-close forward returns from the candidate signal close, because the hypothesis concerns broad / median-stock fragility more directly than a cap-weighted growth index.

No threshold is inferred from these windows.

| Signal date | Same-day structure | Pre-outcome state | +1D CSI1000 | +3D CSI1000 | +5D CSI1000 | Diagnostic |
|---|---|---|---:|---:|---:|---|
| 2026-04-13 | >3,500 decliners, index mixed/slightly positive, turnover contraction, selective AI/battery strength | legacy diagnostic | +1.49% | +2.58% | +4.14% | FALSE POSITIVE if breadth alone is used |
| 2026-04-15 | 3,541 decliners, Shanghai flat, ChiNext -1.22%, tech leaders weak, small/mid-cap weakness, slight turnover expansion, defensive rotation | INTERNAL_FRAGILITY_CONFIRMED | +1.56% | +3.10% | +4.63% | FALSE ALARM: multi-evidence label still too permissive |
| 2026-05-26 | >4,000 decliners, micro/small-cap stress, high-level momentum failures, index damage partly masked by tech weights | legacy diagnostic | -1.62% | -3.21% | -3.48% | STRONG POSITIVE diagnostic |
| 2026-06-25 | growth indices strong, turnover very high, >4,200 decliners, leadership highly concentrated in tech weights | legacy diagnostic | -2.54% | -0.18% | -2.27% | POSITIVE but path mean-reverted at +3D |
| 2026-09-03 | >3,500 decliners, indices ~flat, low/contracting turnover, high-level speculative names weakening | legacy diagnostic | -1.21% | +0.78% | -0.16% | MILD / TRANSIENT fragility |
| 2026-09-09 | >3,600 decliners, headline indices near flat, micro/speculative weakness, momentum failures, low/contracting turnover, rotation to agriculture/shipping/coal | INTERNAL_FRAGILITY_CONFIRMED | -0.80% | -2.36% | -0.80% | MILD WARNING; full CONFIRMED response would be too aggressive |

## Raw CSI1000 closes used

### 2026-04-13 signal
- signal close: 8025.57
- +1D (04-14): 8144.76
- +3D (04-16): 8232.98
- +5D (04-20): 8357.81

### 2026-04-15 signal — preregistered before outcomes
- signal close: 8106.16
- +1D (04-16): 8232.98
- +3D (04-20): 8357.81
- +5D (04-22): 8481.24

### 2026-05-26 signal
- signal close: 8687.25
- +1D (05-27): 8546.51
- +3D (05-29): 8408.74
- +5D (06-02): 8384.78

### 2026-06-25 signal
- signal close: 8825.92
- +1D (06-26): 8601.41
- +3D (06-30): 8809.79
- +5D (07-02): 8625.33

### 2026-09-03 signal
- signal close: 7600.10
- +1D (09-04): 7508.09
- +3D (09-08): 7659.61
- +5D (09-10): 7587.75

### 2026-09-09 signal — preregistered before outcomes
- signal close: 7648.80
- +1D (09-10): 7587.75
- +3D (09-14): 7468.30
- +5D (09-16): 7587.43

## Evidence interpretation

### What failed

A rule equivalent to:

`if decliners > some large count AND index >= flat -> INTERNAL_FRAGILITY_CONFIRMED`

is rejected.

The new 2026-04-15 preregistered control is stronger evidence against over-eager confirmation: breadth weakness, technology-leadership deterioration, small/mid-cap weakness and defensive rotation all coexisted, yet CSI1000 subsequently gained at +1D / +3D / +5D. This means the current qualitative definition of `CONFIRMED` is still too permissive if it does not distinguish temporary profit-taking from persistent risk-budget contraction.

### What remains plausible

The useful signal appears to require not only multiple deterioration channels, but also evidence of **persistence / capital-withdrawal severity**. Current candidate dimensions are:

1. breadth divergence;
2. leadership concentration / crowding;
3. leadership deterioration, failed continuation, or high-level momentum break;
4. small-cap / median-stock weakness;
5. turnover state — active distribution versus low-liquidity drift versus healthy rotation;
6. external or derivative stress when present;
7. persistence across sessions or inability of breadth / leaders to repair.

The 2026-05-26 case remains materially more informative than 2026-04-15 because leadership failure and small-cap stress were followed by persistent broad deterioration rather than immediate repair.

The 2026-06-25 case demonstrates that a strong cap-weighted growth index can coexist with broad fragility, but also that path risk is not monotonic: +1D damage can partially mean-revert before weakness returns.

The 2026-09-09 non-tech / rotation case is useful because it removes dependence on AI/technology leadership. It produced a real +3D drawdown, but most of the damage repaired by +5D. That is more consistent with a `MILD_WARNING` than a full tail-risk state.

## Revised research semantics candidate

The current binary WATCH / CONFIRMED split is insufficient. Retain it for compatibility, but research an additional severity/persistence axis:

- `INTERNAL_FRAGILITY_WATCH`: divergence exists, confirmation incomplete.
- `INTERNAL_FRAGILITY_CONFIRMED_LOW_SEVERITY`: multiple deterioration channels align, but liquidity stress / persistence evidence is weak.
- `INTERNAL_FRAGILITY_CONFIRMED_HIGH_SEVERITY`: multiple channels align with active distribution, external/derivative stress, or persistent failure to repair.
- `ACTIVE_DE_RISKING`: price weakness + expanding turnover / broad selling pressure.
- `REPAIR`: stress background remains, but price acceptance, breadth and leadership are improving.

These labels are not production rules and have no frozen thresholds.

## Current decision consequence candidate

Internal fragility should affect risk budget before stock selection:

- WATCH: reduce chase tolerance; do not automatically cut positions.
- CONFIRMED_LOW_SEVERITY: modestly reduce new high-beta budget; require stronger RS/catalyst evidence; preserve ability to participate in repair.
- CONFIRMED_HIGH_SEVERITY / ACTIVE_DE_RISKING: prioritize capital preservation and relative-strength survivors; sharply restrict new high-beta risk.
- REPAIR: re-open attack candidates selectively; do not restore full risk budget merely because headline indices rebound.

## Tail-risk save vs false-alarm cost

The next validation stage must score two separate objectives:

1. `TAIL_RISK_SAVE`: downside avoided in severe stress windows by reducing risk budget before/into persistent de-risking.
2. `FALSE_ALARM_COST`: upside forgone when a fragility signal is followed by fast repair, as in 2026-04-15.

A model that only looks good on crash windows but frequently exits recoverable pullbacks is not acceptable.

## Sources / provenance

Same-day market structure was reconstructed from contemporaneous public market reports. Historical index outcomes were sourced from previously captured 东方财富 historical K-line data and cross-checked where needed with public index-history sources. The 2026-04-15 and 2026-09-09 state labels were committed in `PREOUTCOME_CASES_V1.md` before forward-return retrieval.

All listed windows are consumed research samples and must not be reused as formal OOS.

## Next step

Before any threshold freeze:

1. keep the preregistered evidence schema fixed;
2. test severity/persistence rather than inventing a new single-day numeric threshold;
3. add at least one deliberately healthy-repair window and one persistent non-tech de-risking window;
4. quantify `TAIL_RISK_SAVE` and `FALSE_ALARM_COST` separately;
5. keep stock-core production weights unchanged.
