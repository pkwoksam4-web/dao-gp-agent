# INTERNAL FRAGILITY V0 — CONTROL MATRIX

Status: RESEARCH_ONLY
Thresholds: NOT_FROZEN
Production use: PROHIBITED

## Outcome metric

For the control matrix, use CSI 1000 close-to-close forward returns from the candidate signal close, because the hypothesis concerns broad / median-stock fragility more directly than a cap-weighted growth index.

No threshold is inferred from these four windows.

| Signal date | Same-day structure | +1D CSI1000 | +3D CSI1000 | +5D CSI1000 | Diagnostic |
|---|---|---:|---:|---:|---|
| 2026-04-13 | >3,500 decliners, index mixed/slightly positive, turnover contraction, selective AI/battery strength | +1.49% | +2.58% | +4.14% | FALSE POSITIVE if breadth alone is used |
| 2026-05-26 | >4,000 decliners, micro/small-cap stress, high-level momentum failures, index damage partly masked by tech weights | -1.62% | -3.21% | -3.48% | STRONG POSITIVE diagnostic |
| 2026-06-25 | growth indices strong, turnover very high, >4,200 decliners, leadership highly concentrated in tech weights | -2.54% | -0.18% | -2.27% | POSITIVE but path mean-reverted at +3D |
| 2026-09-03 | >3,500 decliners, indices ~flat, low/contracting turnover, high-level speculative names weakening | -1.21% | +0.78% | -0.16% | MILD / TRANSIENT fragility |

## Raw CSI1000 closes used

### 2026-04-13 signal
- signal close: 8025.57
- +1D (04-14): 8144.76
- +3D (04-16): 8232.98
- +5D (04-20): 8357.81

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

## Evidence interpretation

### What failed

A rule equivalent to:

`if decliners > some large count AND index >= flat -> INTERNAL_FRAGILITY_CONFIRMED`

is rejected as a research shortcut.

The 2026-04-13 control produces a clear false positive: breadth was weak, but CSI1000 subsequently rose at 1D / 3D / 5D horizons.

### What remains plausible

The useful signal appears to require multiple independent pieces of evidence, especially:

1. breadth divergence;
2. leadership concentration / crowding;
3. leadership deterioration, failed continuation, or high-level momentum break;
4. small-cap / median-stock weakness;
5. turnover state (active distribution versus low-liquidity drift);
6. external or derivative stress when present.

The 2026-05-26 case is materially more informative than 2026-04-13 because breadth weakness coexisted with leadership failure and small-cap stress.

The 2026-06-25 case demonstrates that a strong cap-weighted growth index can coexist with broad internal fragility, but it also shows why a one-day crash forecast is too narrow: the +3D path repaired before weakening again by +5D.

The 2026-09-03 case demonstrates a lower-severity state: broad weakness existed, but subsequent damage was shallow / transient rather than a persistent unwind.

## Current research semantics

- `INTERNAL_FRAGILITY_WATCH`: divergence exists, but confirmation is incomplete.
- `INTERNAL_FRAGILITY_CONFIRMED`: multiple independent deterioration signals align.
- `ACTIVE_DE_RISKING`: price weakness + expanding turnover / broad selling pressure.
- `REPAIR`: stress persists in background, but price acceptance and breadth are improving.

These are categorical research states, not numeric production rules.

## Current decision consequence candidate

Internal fragility should affect risk budget before it affects stock selection:

- WATCH: reduce chase tolerance; do not automatically cut positions.
- CONFIRMED: reduce new high-beta budget; demand stronger relative-strength and catalyst evidence.
- ACTIVE_DE_RISKING: prioritize capital preservation and relative-strength survivors.
- REPAIR: re-open attack candidates selectively; do not restore full risk budget merely because indices rebound.

## Sources / provenance

Same-day market structure was reconstructed from contemporaneous public market reports (primarily 财联社) and historical index bars from 东方财富 historical K-line endpoints. The specific historical windows are already consumed by research and must not be reused as formal OOS.

## Next step

Before any threshold freeze:

1. add at least one more deliberately selected false-positive control;
2. add a non-tech / non-AI fragility window;
3. preregister the evidence fields before testing the next unused window;
4. separate `tail-risk avoidance value` from `false-alarm cost`;
5. keep stock-core production weights unchanged.
