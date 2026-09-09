# Audit Remediation V1 — QFQ Probe Registry Evidence Amendment

Date: 2026-09-09
Status: EVIDENCE_CORRECTION
Parent spec: `docs/superpowers/specs/2026-09-09-audit-remediation-v1-design.md`

## Correction

The adversarial review initially described an earlier V4.77 QFQ semantic probe as a second exact `fixed5` set and associated it with a five-symbol Shanghai candidate list. Subsequent source recovery did not substantiate that assertion.

Authoritative recovered V4.71–V4.77 evidence establishes:

- `QFQ_FACTOR_PILOT_V471` contains explicit semantic-pilot evidence for `002938.SZ` and `300592.SZ`.
- `FORMAL_GATE_CHECKPOINT_V477` explicitly tracks those two semantic statuses and keeps Sample50 scaling closed until the independent Sina route closes.
- No recovered authoritative file in the review surface establishes the previously asserted Shanghai five-symbol list as an exact V4.77 QFQ `fixed5` contract, nor supplies its branch/run identity.

Therefore Audit Remediation V1 MUST NOT manufacture `QFQ_SEMANTIC_FIXED5_V477` as a verified registry entry.

## Revised registry rule

`FIXED_PROBE_REGISTRY_V1.json` will:

1. register `RAW_PITST_SOURCE_FIXED5_V482` as the currently verified exact fixed-five probe, with its exact five symbols and GitHub run/artifact lineage;
2. register `QFQ_SEMANTIC_PILOT_V471_V477` as a distinct semantic pilot with the currently evidenced symbols `002938.SZ` and `300592.SZ`, explicitly `NOT_AN_EXACT_FIXED5_CONTRACT`;
3. record the earlier QFQ fixed-five assertion as `UNVERIFIED_PRIOR_ASSERTION_NOT_FREEZE_ELIGIBLE` without persisting the unsupported candidate symbol list as fact;
4. prohibit any bare `fixed5` label in promotion artifacts.

This amendment strengthens the parent design: ambiguity is eliminated by refusing unsupported exactness, not by assigning a precise identifier to an unproven symbol set.
