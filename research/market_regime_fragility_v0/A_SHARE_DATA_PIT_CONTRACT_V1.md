# A-SHARE DATA PIT CONTRACT V1

Status: GOVERNANCE_FROZEN
Production use: PROHIBITED
Formal OOS: NO
Purpose: prevent survivorship, revised-history and publication-time leakage in A-share research inputs

## 1. Scope

This contract governs any historical or prospective input used by the market-regime, theme, relative-strength, timing, stock-ranking or execution-evaluation layers when that input can change over time or depends on historical eligibility.

The contract covers:

1. decision-date stock universe;
2. listing / delisting / ST / suspension / board status;
3. price and corporate-action history;
4. financial-report and earnings-announcement information;
5. mutable vendor-derived fields, including vendor capital-flow fields;
6. source snapshot identity, retrieval timestamp and content hash.

It does not freeze numeric liquidity/new-listing thresholds or production portfolio limits.

## 2. Decision-date universe is PIT data

A historical decision may use only securities that were eligible under the versioned universe policy and security state known at that decision timestamp.

The project may not reconstruct a past universe from today's surviving ticker list.

Required state includes, when relevant:

- listed / not-yet-listed status;
- delisting / delisting-risk status;
- ST-type status;
- suspension status;
- board / venue identity;
- PIT price-limit rule identity;
- versioned new-listing policy result;
- versioned liquidity policy result.

`UNIVERSE_PIT_SNAPSHOT_V1` produces the required deterministic snapshot hash and explicit eligible / ineligible / unresolved sets.

An unresolved record is not silently treated as eligible.

## 3. Price and corporate-action data

Back-adjusted or forward-adjusted vendor price histories are mutable representations, not immutable historical facts.

A return feature used for a decision must be reproducible from one of these two admissible carriers:

### A. Raw-price path

- raw historical prices;
- corporate-action data available as of the relevant decision timestamp;
- versioned adjustment algorithm;
- archived input identities / hashes.

### B. Vendor-adjusted snapshot path

Archive the exact fetched vendor series with:

- retrieval timestamp;
- adjustment mode;
- source / endpoint identity;
- requested date range;
- content hash;
- enough raw payload or immutable artifact identity to reproduce the feature calculation.

A later API refresh that rewrites historical QFQ/HFQ values may not silently replace the series that generated an earlier signal.

If the original snapshot cannot be reproduced, the historical feature is `UNVERIFIED`, not retroactively repaired from the latest adjusted series.

## 4. Financial information publication-time rule

Accounting period end is not the information-availability date.

A fundamental field may enter a decision only from the timestamp at which the corresponding information was public and available to the model.

The data model must distinguish at least:

- earnings preview / guidance;
- preliminary earnings announcement;
- statutory periodic report;
- correction / restatement / revised filing.

A later statutory report or restatement may not be projected backward into an earlier decision timestamp.

For each decision-active fundamental value, retain source identity, public timestamp and snapshot/hash.

## 5. Mutable vendor-derived fields

Vendor fields such as capital-flow, order-size distribution, sector labels or other calculated historical fields may be revised after first publication.

If a mutable vendor field affects a decision:

- archive the fetched snapshot at decision time;
- record retrieval timestamp and source identity;
- store deterministic content hash;
- do not substitute the provider's latest historical value for the original snapshot in formal evaluation.

If the provider cannot supply immutable history and no archived snapshot exists, the past value is `UNVERIFIED`.

Vendor capital-flow fields remain vendor-defined net-flow / distribution measures. They do not identify institutions or prove institutional accumulation/distribution.

## 6. PIT timestamps and time zones

Every mutable record used in evaluation must carry:

- timezone-aware observation / publication timestamp;
- decision cutoff;
- PIT-valid flag;
- provenance.

An observation timestamp after the decision cutoff is ineligible even if it describes an earlier accounting period or trading date.

Naive timestamps cannot be accepted as formal PIT evidence without a separately bound timezone contract.

## 7. Snapshot immutability and hashing

Formal evaluation manifests must bind feature inputs to immutable artifact identities or deterministic hashes.

At minimum, retain hashes for:

- universe snapshot;
- classifier evidence ledger;
- mutable adjusted-price carrier when used;
- mutable vendor-derived carrier when used;
- evaluation set.

Appending future data must not alter the historical record/hash that supported a past decision.

## 8. Missing / revised / conflicting data

Fail-closed rules:

- missing original snapshot -> `UNVERIFIED`;
- conflicting sources without adjudication -> `UNRESOLVED`;
- post-cutoff correction -> unavailable to the original decision, but may be logged as later evidence;
- current-state ticker metadata may not overwrite decision-date metadata;
- unresolved policy parameters may not default to today's policy.

## 9. Evaluation requirement

Any future economic or predictive comparison must report the proportion of decisions excluded or unresolved because PIT evidence was unavailable.

A model must not appear stronger merely because difficult historical rows were silently dropped after outcome review.

Exclusion reasons must be fixed by the data contract, not by realized performance.

## 10. Production blocker

No feature family that relies on mutable history is eligible for production promotion until its snapshot/archive path is operational and timestamp-audited.

This document freezes the governance semantics only. It does not claim that all required historical snapshots already exist.
