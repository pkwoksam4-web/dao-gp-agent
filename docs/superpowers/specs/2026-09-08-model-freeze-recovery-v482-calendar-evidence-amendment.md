# Model Freeze Recovery V4.82 — Calendar Evidence Amendment

This amendment replaces only the calendar-evidence source selection in `2026-09-08-model-freeze-recovery-v482-design.md`. All fail-closed model, scope-intent, promotion, and no-OOS-exposure rules remain unchanged.

## Evidence discovered during TDD

The repository already contains the V4.80 frozen-calendar contract in `scripts/frozen_calendar_v480.py`:

- `FROZEN_CALENDAR_SHA256 = 0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0`
- `FROZEN_CALENDAR_N = 1426`
- first date `2020-06-01`
- last date `2026-04-17`
- the legacy hash payload is the sorted date sequence with a newline after every date, including the final date.

The successful V4.80 final-audit workflow run `33977325822` downloaded merged PIT/ST evidence, verified this exact contract, materialized `OFFICIAL_A_SHARE_OPEN_DATES_V357.csv`, and uploaded it inside artifact `gp-pit-st-v480-final-audit` (artifact id `9972698555`). That artifact is still available.

The repository transport wrappers are not equivalent authoritative copies:

- `data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.b64` is smaller and its decoded gzip fails CRC validation.
- `data/OFFICIAL_A_SHARE_OPEN_DATES_V357.csv.gz.hex` is a different size.

Therefore requiring the two repository wrappers to decode to identical bytes would incorrectly reject an already verified V4.80 calendar solely because a non-authoritative transport copy is damaged.

## Revised authoritative source rule

For Model Freeze Recovery V4.82, the authoritative Formal calendar input is:

`gp-pit-st-v480-final-audit` from successful run `33977325822` → `OFFICIAL_A_SHARE_OPEN_DATES_V357.csv`.

Recovery must validate the CSV against the existing frozen contract before using it:

1. exactly 1426 unique strictly increasing ISO dates;
2. first date exactly `2020-06-01`;
3. last date exactly `2026-04-17`;
4. legacy newline-terminated SHA256 exactly `0bfa32175dfccbd24d30eb7ceb0605f6cde2ed0bcc31ac2cac61479ba812add0`.

Only after all four checks pass is `recoverable.formal_calendar = true`.

## Two hash namespaces

Do not conflate the historical frozen-calendar hash with the recovery canonical hash.

- `legacy_frozen_calendar_sha256` is the existing V4.80 contract hash over `date + "\n"` for every date, including the last.
- `formal_calendar_sha256` is the Model Freeze Recovery semantic hash over the same 1426 dates joined by `"\n"` with **no trailing newline**, matching the recovery/OOS canonicalization rule.

Both must be recorded in checkpoint evidence. The legacy hash proves continuity with V4.80; the semantic hash is the recovery subsystem's canonical binding.

## Repository wrappers

The `.b64` and `.hex` files remain provenance diagnostics only. Their corruption/mismatch must be reported in evidence but must not override a successfully verified authoritative final-audit calendar CSV.

They cannot be used to extend the calendar beyond `2026-04-17` and cannot clear `OOS_CALENDAR_COVERAGE_MISSING`.

## OOS coverage consequence

Because the authoritative frozen Formal calendar ends on `2026-04-17`, it does **not** cover the frozen OOS intent through `2026-09-08`.

The production recovery checkpoint is therefore expected to include:

- `OOS_CALENDAR_COVERAGE_MISSING`
- `STRATEGY_CODE_MISSING`
- `PARAMETER_SET_MISSING`
- `FACTOR_DEFINITION_MISSING`

until an independently verified OOS-capable official calendar and the genuine three strategy-side assets are recovered.

## TDD correction

A new RED test must first prove that authoritative CSV recovery validates the legacy contract and produces a distinct semantic canonical hash. Only then may the production CLI/workflow switch from repository wrappers to the final-audit CSV artifact.
