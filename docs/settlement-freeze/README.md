# Settlement freeze packet — 2026-10-28 owner decision

**Status: PROPOSAL_NOT_FROZEN.** These drafts are for the owner to approve or change on 2026-10-28 before any result prices are inspected for evaluation. They contain no cohort outcomes, rank IC, or aggregate performance calculations. A passing CI run is not a research result or authorization.

## Decisions for the owner

1. [Outcome price source pair](01-price-sources.md)
2. [Corporate-action rule](02-corporate-actions.md)
3. [Evaluation baseline](03-evaluation-baseline.md)
4. [Minimum gain, power, and inference unit](04-threshold-and-power.md)
5. [One-time historical lookback re-pull and reconciliation specification](05-lookback-rerun.md)

The first four documents define the outcome policy. The fifth is an implementation specification only; it does not authorize database access or writes.

## Freeze record

On approval, record the exact decision timestamp in Asia/Shanghai, the approved values, and the merged commit SHA in issue #28. Hash the merged decision files with SHA-256 and record that digest there. Any item not approved stays `NOT_FROZEN`; do not inspect outcome results to choose among alternatives.

The proposed source pair, thresholds, and statistical assumptions remain proposals until the owner records the freeze.
