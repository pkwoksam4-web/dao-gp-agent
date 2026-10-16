# SOURCE RECOVERY CHECKPOINT — 2026-10-16

Status: EVIDENCE_IDENTITY_BOUND / ROW_CARRIERS_NOT_CURRENTLY_RETRIEVABLE
Scope: A-share Universe / Tradability source recovery
Production use: PROHIBITED
Formal OOS authorization: NO

## 1. Purpose

Separate three facts that must not be conflated:

1. a historical artifact was successfully produced and audited;
2. its exact artifact identity/digest is still known;
3. its row bytes are still retrievable today.

Only (1) and (2) remain true for the key historical carriers checked in this recovery pass. Current GitHub Actions retention no longer exposes their row bytes.

## 2. PIT-ST / calendar carrier

Historical evidence identity:

- run: `33977325822`
- artifact: `gp-pit-st-v480-final-audit`
- artifact id: `9972698555`
- ZIP SHA256: `a86d807829deb393e012e93fea44637cefd1759c973fa109e2a728647fa83f58`
- formal calendar semantic SHA256: `5a872a47cf7a338cc48aa628b8de46053fddc3ed161a2617550199d0607efae7`
- recorded audit: lifecycle `847/847 PASS`, calendar `1426/1426 PASS`, missing required dates `0`, duplicate daily keys `0`, invalid daily rows `0`, outside-calendar rows `0`, transition cross-check `6/6 PASS`.

Current recovery result:

- direct artifact retrieval by id `9972698555`: `404 Not Found`.
- checkpoint tree `gp/dao2-d-label-status@2a7056ffd61885046e34dc1494bc668143d96793` contains audit scripts, scope files, evidence/manifests and exact V4.82 point-correction documentation, but not the full historical PIT-ST row panel.

Ruling:

`PIT_ST_SEMANTICS_AND_AUDIT_PROVENANCE = BOUND`

`PIT_ST_ROW_CARRIER_CURRENTLY_RETRIEVABLE = NO`

Do not regenerate current BaoStock history and silently call it the original artifact. A regenerated panel would be a new carrier/version and must be compared independently against the frozen digest-level evidence available from the old audit.

## 3. Full RAW carrier

Historical evidence identity recovered from `docs/gp12-formal-input-readiness-v1.md`:

- run: `34192233633`
- workflow: `GP V4.82 Existing Shard Reaudit + Liquidity Apply`
- head commit: `8e19520d5d3d942496ac8be75a86197fa8cefbe5`
- artifact: `gp-sohu-full-raw-v482-reaudit`
- artifact id: `10042614517`
- ZIP SHA256: `cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550`
- recorded coverage: `847` symbols, `1,011,607` trade rows.

Current recovery result:

- direct artifact retrieval by id `10042614517`: `404 Not Found`.
- querying `https://api.github.com/repos/pkwoksam4-web/dao-gp-agent/actions/runs/34192233633/artifacts` returns `total_count = 0`.

Ruling:

`SOHU_RAW_AUDIT_IDENTITY = BOUND`

`SOHU_RAW_ROW_CARRIER_CURRENTLY_RETRIEVABLE = NO`

The old row-level positive-volume evidence may be cited only through existing audited derived evidence/point corrections. It is not currently available as a general historical execution-side row source.

## 4. Frozen liquidity carrier

Historical evidence identity recovered from the same readiness chain:

- run: `34192233633`
- artifact: `gp-liquidity-80m-v482`
- artifact id: `10042615093`
- ZIP SHA256: `a041d50ab2c9bbbe5f129d9afae87e817de0b1d8073c86cf829427f031bbc37b`
- recorded panel rows: `1,207,822`
- frozen threshold context: `80,000,000 CNY` liquidity contract.

Current recovery result:

- direct artifact retrieval by id `10042615093`: `404 Not Found`.
- parent run artifact list currently contains `0` artifacts.

Ruling:

`LIQUIDITY_AUDIT_IDENTITY = BOUND`

`LIQUIDITY_ROW_CARRIER_CURRENTLY_RETRIEVABLE = NO`

Do not treat the old 80M contract as proof of buy-side or sell-side executable liquidity for `A_SHARE_TRADABILITY_GATE_V1`; the new gate requires side-specific execution evidence and is semantically stricter.

## 5. BaoStock turnover carrier cross-check

Separate binding manifest:

`data/GP12_AMOUNT_TURNOVER_BINDING_V1.json`

Historical artifact:

- artifact: `gp12-baostock-turnover-full-v482`
- artifact id: `10383758045`
- archive SHA256 recorded by the binding manifest.

Current recovery result:

- direct artifact retrieval by id `10383758045`: `404 Not Found`.

This confirms that the current retention issue is not limited to one artifact family.

## 6. Recovery policy

No row carrier may be labelled `RECOVERED_ORIGINAL` unless byte identity can be verified against an immutable original digest or a committed byte-identical source.

Allowed future statuses:

- `ORIGINAL_RETRIEVED_HASH_MATCH`
- `COMMITTED_EQUIVALENT_HASH_MATCH`
- `REGENERATED_NEW_CARRIER_CROSSCHECKED`
- `EVIDENCE_IDENTITY_ONLY_ROW_BYTES_UNAVAILABLE`

A regenerated carrier is never silently substituted for an expired original.

For mutable/vendor/API sources, regeneration after the fact does not establish historical PIT identity. It may provide a comparison/control source only.

## 7. Practical consequence for current research

The following are source-bound semantically but not row-integrated today:

- historical `isST`;
- historical `tradestatus`;
- old RAW actual-trade panel;
- frozen liquidity panel.

The new research gates therefore remain:

- `UNIVERSE_PIT_INTEGRATION = INCOMPLETE`
- `SIDE_SPECIFIC_TRADABILITY_INTEGRATION = INCOMPLETE`
- `FORMAL_EVALUATION = BLOCKED`
- `PRODUCTION_AUTHORIZED = FALSE`

This checkpoint does not invalidate the old audit conclusions. It prevents those conclusions from being misrepresented as currently replayable row-level inputs.

## 8. Next route

Do not spend another loop searching the same expired artifact ids.

Only reopen row-carrier recovery if one of the following appears:

1. a committed byte carrier matching the frozen digest;
2. an external immutable archive with exact original bytes;
3. an already-connected project store holding the original files;
4. a regenerated source that is explicitly admitted only as a new carrier after independent cross-checking, never as the original.

Until then, continue governance work that does not require those rows: downgrade/change-control, manual-override logging, comparator/null design, and non-numeric hard-risk contract refinement.
