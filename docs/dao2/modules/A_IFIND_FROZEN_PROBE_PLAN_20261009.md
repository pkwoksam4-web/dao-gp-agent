# DAO2 A iFinD Frozen Probe Plan — 2026-10-09

This plan is execution-scoped to Module A only.

## Frozen authorities

- Residual scope: `data/GP12_CANDIDATE_MAIN_NET_FLOW_RESIDUAL_LEDGER_V1.json`
- Key manifest: `data/dao2/modules/A_16_KEY_SET_HASH_MANIFEST_20261007.json`
- Frozen identity controls: `data/dao2/modules/A_JESSICA_KNOWN_ROW_CONTROL_SCOPE_V1.json`

## Required behavior

1. Read exactly 8 frozen controls (32 field comparisons).
2. Test only predefined candidate field mappings based on iFinD native historical amount indicators and predefined snake_case amount variants.
3. For each mapping use one global scale, limited to `1`, `0.0001`, or `10000`.
4. PASS requires exactly `32/32` exact and `mismatch=0`; no tolerance, rounding fit, affine transform, date/symbol-specific scale, or result-driven field guessing.
5. Verify refresh-token presence, refresh success, historical control readability, and non-null/non-permission-denied values before identity evaluation.
6. Only after identity PASS load the 16 residual keys from the authoritative ledger; never from a handwritten list.
7. Persist raw response, SHA256, endpoint/query provenance, mapping, scale, and derived `main_net_flow_cny` for every residual row.
8. Partial admission is immediate per exact residual row; do not wait for 16/16.
9. On entitlement/history failure return `IFIND_DIRECT_BLOCKED_ENTITLEMENT_OR_HISTORY`; on readable-but-no-unique-identity return `IFIND_DIRECT_REJECT_SEMANTIC_IDENTITY`.

FFD remains evidence/cross-check only and is not an admission source for this workflow.
