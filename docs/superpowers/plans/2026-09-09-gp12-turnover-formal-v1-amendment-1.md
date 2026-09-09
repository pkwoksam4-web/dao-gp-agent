# GP12 Turnover Formal V1 Plan Amendment 1

This amendment is part of the approved implementation plan and supersedes only the post-Formal source-record handling described in Task 1 of `2026-09-09-gp12-turnover-formal-v1.md`.

## Reason

Reverse-checking the plan against the live source contract exposed a false-negative risk: on 2026-09-09 the Sina historical share-amount endpoint may legitimately return dated share-capital records after the Formal boundary `2026-04-17`. Rejecting the entire payload merely because such records are present would make a valid historical source unusable.

## Correct rule

1. Exact raw response bytes are retained and SHA256-bound without truncation.
2. `parse_share_amount_bytes` may decode valid positive dated records on either side of the Formal boundary.
3. `build_symbol_evidence` creates the normalized Formal record set by retaining only `record_date <= 2026-04-17`.
4. Post-Formal records are counted as `post_formal_record_n` but their values are not emitted into the Formal normalized record set and cannot affect PIT resolution, coverage, materialization, or readiness.
5. A payload is invalid for malformed JSONP, invalid dates, duplicate record dates, nonfinite values, or nonpositive share values; it is not invalid merely because it contains later records.
6. The PIT resolver continues to use only the latest retained record satisfying `record_date <= trade_date`.

This amendment does not loosen the OOS boundary. It makes the boundary stricter by preserving the source bytes while preventing post-Formal values from influencing any Formal output.
