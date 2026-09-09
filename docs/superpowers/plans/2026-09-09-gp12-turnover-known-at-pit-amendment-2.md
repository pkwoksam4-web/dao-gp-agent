# GP12 Turnover Known-At PIT Amendment 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ShareAmount-date-only turnover PIT resolution with a dual-Sina-source known-at chain that binds historical circulating-A-share values to StockStructure announcement dates before any 847-symbol production attempt.

**Architecture:** Keep `gp12_sina_share_amount_v1.py` responsible only for ShareAmount bytes/parsing. Add a focused StockStructure parser and a focused cross-source known-at binder. Turnover materialization consumes already-bound known-at states; the workflow proves the full chain first on `600000.SH`, then and only then permits an 847-symbol production job.

**Tech Stack:** Python 3.12, stdlib `decimal`, `datetime`, `html.parser`/`re`, `unittest`, `requests`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-09-gp12-turnover-known-at-pit-amendment-2-design.md`

## Global Constraints

- Formal range remains exactly `2020-06-01 .. 2026-04-17`.
- Frozen universe SHA256 remains `dfe5c75692d38e5fde7cd5c32eb2ed090a8ab6dffcfd41d5ebda07dc2d6d96fb`.
- Signed RAW volume source remains `gp-sohu-full-raw-v482-reaudit`, SHA256 `cee7e91f1fda605f7c3bdf41c3f4a7796feeae83f8c3702e50900e6af3fa9550`, expected rows `1,011,607`.
- ShareAmount values remain units of 10,000 shares and are multiplied by exactly `10,000` only after positive finite validation.
- StockStructure `公告日期` is a separate known-at input; ShareAmount `date` alone can never establish `PIT_VERIFIED`.
- `known_at = max(change_date, announcement_date)`.
- A trade date may use a state only when `change_date <= trade_date` and `known_at <= trade_date`.
- Post-Formal source rows may remain in raw bytes but cannot influence Formal materialization or readiness.
- `model_freeze_allowed = false` and `oos_metrics_allowed = false` throughout this subsystem.
- No Eastmoney/current-capital/proxy fallback.

---

### Task 1: Parse Sina StockStructure into deterministic historical columns

**Files:**
- Create: `scripts/gp12_sina_stock_structure_v1.py`
- Create: `scripts/test_gp12_sina_stock_structure_v1.py`
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml`

**Interfaces:**
- Consumes: `symbol: str`, raw HTML bytes from `https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_StockStructure/stockid/{code}.phtml`.
- Produces: `parse_stock_structure_bytes(symbol: str, raw: bytes) -> list[dict]`, `fetch_stock_structure(session, symbol, timeout=20, retries=3) -> tuple[bytes|None, dict]`.
- Normalized row keys: `symbol`, `change_date`, `announcement_date`, `change_reason`, `circulating_a_10k_display`, `circulating_a_display_scale`.

- [ ] **Step 1: Write the failing parser tests**

Use a fixture whose visible Sina table contains two aligned columns:

```python
HTML = b'''<table>
<tr><td>\xb1\xe4\xb6\xaf\xc8\xd5\xc6\xda</td><td>20241231</td><td>20250331</td></tr>
<tr><td>\xb9\xab\xb8\xe6\xc8\xd5\xc6\xda</td><td>20250104</td><td>20250403</td></tr>
<tr><td>\xb1\xe4\xb6\xaf\xd4\xad\xd2\xf2</td><td>\xd5\xae\xd7\xaa\xb9\xc9</td><td>\xd5\xae\xd7\xaa\xb9\xc9</td></tr>
<tr><td>\xc1\xf7\xcd\xa8A\xb9\xc9(\xc0\xfa\xca\xb7\xbc\xc7\xc2\xbc)</td><td>2935217.83 \xcd\xf2\xb9\xc9</td><td>2935217.900 \xcd\xf2\xb9\xc9</td></tr>
</table>'''

def test_parse_stock_structure_columns():
    rows = mod.parse_stock_structure_bytes('600000.SH', HTML)
    self.assertEqual(rows[0]['change_date'], '2024-12-31')
    self.assertEqual(rows[0]['announcement_date'], '2025-01-04')
    self.assertEqual(rows[0]['circulating_a_10k_display'], '2935217.83')
    self.assertEqual(rows[0]['circulating_a_display_scale'], 2)
```

Also add tests that reject: missing announcement row, malformed `YYYYMMDD`, nonpositive circulating-A value, unequal column counts, and duplicate `(change_date, announcement_date, value)` rows.

- [ ] **Step 2: Run RED**

Run in workflow:

```bash
cd scripts
python -m unittest -v test_gp12_sina_stock_structure_v1.py
```

Expected: `ModuleNotFoundError: No module named 'gp12_sina_stock_structure_v1'` while all existing turnover tests remain untouched.

- [ ] **Step 3: Implement the minimal parser/fetcher**

Implement exact helpers:

```python
STOCK_STRUCTURE_URL = 'https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_StockStructure/stockid/{code}.phtml'

def parse_stock_structure_bytes(symbol: str, raw: bytes) -> list[dict]: ...

def fetch_stock_structure(session, symbol: str, timeout: int = 20, retries: int = 3) -> tuple[bytes | None, dict]: ...
```

Decode using `gb18030` first and `utf-8-sig` second. Parse table rows by normalized text labels `变动日期`, `公告日期`, `变动原因`, and `流通A股(历史记录)`. Convert dates from `YYYYMMDD` to canonical ISO. Preserve the displayed decimal as a string and its decimal scale; reject `--` for rows that otherwise claim a dated state.

- [ ] **Step 4: Run GREEN plus existing regression tests**

Run:

```bash
cd scripts
python -m unittest -v \
  test_gp12_sina_stock_structure_v1.py \
  test_gp12_sina_share_amount_v1.py \
  test_gp12_turnover_formal_v1.py \
  test_gp12_turnover_readiness_bind_v1.py \
  test_gp12_formal_input_readiness_v1.py
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/gp12_sina_stock_structure_v1.py scripts/test_gp12_sina_stock_structure_v1.py .github/workflows/gp12-turnover-formal-v1.yml
git commit -m "feat(gp12): parse Sina stock-structure known-at evidence"
```

---

### Task 2: Uniquely bind ShareAmount rows to StockStructure known-at rows

**Files:**
- Create: `scripts/gp12_share_known_at_v1.py`
- Create: `scripts/test_gp12_share_known_at_v1.py`
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml`

**Interfaces:**
- Consumes: ShareAmount rows from `parse_share_amount_bytes`, StockStructure rows from Task 1, and the two raw SHA256 identities.
- Produces: `bind_known_at_states(symbol: str, share_rows: list[dict], structure_rows: list[dict], share_raw_sha256: str, structure_raw_sha256: str, formal_end: str = '2026-04-17') -> dict` and `resolve_known_at_state(states: list[dict], trade_date: str) -> dict | None`.

- [ ] **Step 1: Write RED tests for exact match and leakage prevention**

```python
def test_late_announcement_delays_state_availability():
    share = [{'symbol':'600000.SH','record_date':'2024-12-31','outstanding_share_shares':29352178302.0}]
    structure = [{'symbol':'600000.SH','change_date':'2024-12-31','announcement_date':'2025-01-04','change_reason':'债转股','circulating_a_10k_display':'2935217.83','circulating_a_display_scale':2}]
    result = mod.bind_known_at_states('600000.SH', share, structure, 'a'*64, 'b'*64)
    state = result['states'][0]
    self.assertEqual(state['known_at'], '2025-01-04')
    self.assertIsNone(mod.resolve_known_at_state(result['states'], '2025-01-03'))
    self.assertEqual(mod.resolve_known_at_state(result['states'], '2025-01-04')['change_date'], '2024-12-31')
```

Add independent tests for: announcement before change date (`known_at == change_date`), page-display precision matching using `Decimal` + `ROUND_HALF_UP`, amount mismatch, missing same-date row, duplicate matching rows, and post-Formal share rows excluded from normalized states.

- [ ] **Step 2: Run RED**

```bash
cd scripts
python -m unittest -v test_gp12_share_known_at_v1.py
```

Expected: module missing.

- [ ] **Step 3: Implement deterministic binding**

Use:

```python
from decimal import Decimal, ROUND_HALF_UP

def _matches_display(api_amount_10k: Decimal, display_text: str, scale: int) -> bool:
    quantum = Decimal(1).scaleb(-scale)
    return api_amount_10k.quantize(quantum, rounding=ROUND_HALF_UP) == Decimal(display_text)
```

For each Formal-era ShareAmount row, collect same-`change_date` structure candidates, apply `_matches_display`, require exactly one match, compute `known_at = max(change_date, announcement_date)`, and return sorted states plus sorted unique blockers. Do not use binary float tolerance.

`resolve_known_at_state` filters `change_date <= trade_date` and `known_at <= trade_date`, then selects the eligible state with greatest `change_date`.

- [ ] **Step 4: Run GREEN + all regressions**

Run all five existing test modules plus the two new modules. Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/gp12_share_known_at_v1.py scripts/test_gp12_share_known_at_v1.py .github/workflows/gp12-turnover-formal-v1.yml
git commit -m "feat(gp12): bind circulating-share states to known-at dates"
```

---

### Task 3: Make turnover consume known-at states instead of ShareAmount dates

**Files:**
- Modify: `scripts/gp12_turnover_formal_v1.py`
- Modify: `scripts/test_gp12_turnover_formal_v1.py`
- Modify: `scripts/gp12_turnover_readiness_bind_v1.py`
- Modify: `scripts/test_gp12_turnover_readiness_bind_v1.py`

**Interfaces:**
- Consumes: states from `gp12_share_known_at_v1.bind_known_at_states`.
- Produces turnover rows with `share_change_date`, `share_announcement_date`, `share_known_at`, `share_amount_raw_sha256`, `stock_structure_raw_sha256`.

- [ ] **Step 1: Write RED tests showing the old resolver leaks**

Add a materializer test with a RAW trade row dated `2025-01-03`, a share change dated `2024-12-31`, and announcement `2025-01-04`. Expected: no turnover row and blocker `TURNOVER_PRIOR_SHARE_RECORD_MISSING`; no state with a future `known_at` may be used.

Add a second row on `2025-01-04`; expected: turnover row exists and carries exact known-at provenance fields.

- [ ] **Step 2: Run RED**

Run only turnover + binder tests. Expected: failure because production materializer still reads `share_record_date`/old states.

- [ ] **Step 3: Replace resolver input contract**

Import `resolve_known_at_state` from `gp12_share_known_at_v1`. Remove Amendment-2 output use of `share_record_date`. Add counter/blocker `TURNOVER_FUTURE_KNOWN_AT_VIOLATION` if a supplied state violates `known_at <= trade_date` after resolution; such a violation is programmer/evidence corruption, never a tolerated row.

Preserve exact formula:

```python
turnover_ratio = volume_shares / outstanding_share_shares
```

- [ ] **Step 4: Run all regression tests**

Expected: all new and old tests PASS; binder still only upgrades `amount_turnover` after a full PASS summary.

- [ ] **Step 5: Commit**

```bash
git add scripts/gp12_turnover_formal_v1.py scripts/test_gp12_turnover_formal_v1.py scripts/gp12_turnover_readiness_bind_v1.py scripts/test_gp12_turnover_readiness_bind_v1.py
git commit -m "fix(gp12): enforce known-at PIT in turnover materialization"
```

---

### Task 4: Add a fail-closed dual-source `600000.SH` live probe

**Files:**
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml`

**Interfaces:**
- Consumes live ShareAmount + StockStructure bytes for `600000.SH`.
- Produces artifact directory `out/known_at_probe/` containing raw files and `SINA_SHARE_KNOWN_AT_PROBE_GP12_V1.json`.

- [ ] **Step 1: Add probe job after contracts**

The probe script must write exact raw bytes to:

```text
out/known_at_probe/600000.SH.share_amount.raw
out/known_at_probe/600000.SH.stock_structure.raw
```

and a JSON summary containing fetch statuses, both raw SHA256 values, parsed row counts, matched-state count, first/last Formal matched change dates, blocker list, `pit_verified`, `formal_feature_ready=false`, `model_freeze_allowed=false`, `oos_metrics_allowed=false`.

- [ ] **Step 2: Enforce terminal probe gate**

Print exactly one of:

```text
DATA_GATE=DUAL_SOURCE_STRUCTURAL_PASS
DATA_GATE=BLOCKED
```

`DUAL_SOURCE_STRUCTURAL_PASS` requires both fetches, both parsers, and at least one unique Formal cross-match. It does **not** make the overall turnover feature ready.

- [ ] **Step 3: Verify live run**

Inspect Actions logs and artifact. Required evidence before Task 5:

- ShareAmount HTTP success;
- StockStructure HTTP success;
- ShareAmount row `2024-12-31` cross-matches StockStructure displayed circulating A-share row at its display precision;
- normalized state records `announcement_date = 2025-01-04` and `known_at = 2025-01-04` for that row, if the live source still reports those exact values;
- probe reports no model/OOS opening.

If any item differs, freeze the observed source bytes and fix parser/matcher under TDD before proceeding. Do not relax the match rule to force a pass.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/gp12-turnover-formal-v1.yml
git commit -m "ci(gp12): prove dual-source known-at share evidence"
```

---

### Task 5: Gate 847-symbol production behind the dual-source probe

**Files:**
- Modify: `.github/workflows/gp12-turnover-formal-v1.yml`
- Modify: `scripts/gp12_sina_share_amount_v1.py` only if batch orchestration needs a reusable helper; do not alter parsing semantics.
- Modify: `scripts/gp12_sina_stock_structure_v1.py` only if batch orchestration needs a reusable helper; do not alter parsing semantics.

**Interfaces:**
- Consumes frozen 847-symbol universe, signed RAW volume artifact, dual-source known-at binders.
- Produces `SINA_SHARE_AMOUNT_MANIFEST_GP12_V1`, normalized dual-source share-state evidence, turnover CSV, `GP12_TURNOVER_FORMAL_V1`, and derived readiness evidence only on full data PASS.

- [ ] **Step 1: Add production job with a hard `needs` gate**

Production must run only when the live probe job completes successfully and exposes `dual_source_gate == DUAL_SOURCE_STRUCTURAL_PASS` as a job output.

- [ ] **Step 2: Collect both sources for exactly the frozen 847 symbols**

For each symbol: conservative retries, request identity, raw bytes, SHA256, parser output, and per-symbol blocker. A network failure remains a data blocker and must not be rewritten as factor/model failure.

- [ ] **Step 3: Bind all Formal-era share states and materialize turnover against signed RAW**

Require exact 847-symbol universe identity and exact RAW row key set of `1,011,607`. Full PASS additionally requires zero cross-source missing/ambiguous/amount-mismatch blockers and zero unresolved turnover rows.

- [ ] **Step 4: Re-run readiness validator only on a full turnover PASS**

Expected semantic outcome after turnover-only success:

```text
TURNOVER_RATIO_UNBOUND removed
MAIN_NET_FLOW_UNBOUND retained
ADJUSTED_CLOSE_PIT_UNVERIFIED retained
F11 remains blocked
candidate_scoring_ready=false
model_freeze_allowed=false
oos_metrics_allowed=false
```

- [ ] **Step 5: Upload all evidence and inspect terminal state**

The workflow may be green while data status is BLOCKED. Logs must print turnover `status`, `pit_state`, materialized row count, blocker list, and both model/OOS safety flags.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/gp12-turnover-formal-v1.yml scripts/gp12_sina_share_amount_v1.py scripts/gp12_sina_stock_structure_v1.py
git commit -m "ci(gp12): gate Formal turnover production on known-at PIT"
```

## Self-Review

- Spec coverage: source separation, unique decimal matching, `known_at`, Formal boundary, row-schema provenance, single-symbol gate, 847 gate, readiness safety, and OOS/model-freeze safety are each mapped to a task.
- Placeholder scan: no `TBD`, `TODO`, generic "handle errors", or undefined future implementation placeholders remain.
- Type consistency: Task 2 produces `bind_known_at_states` / `resolve_known_at_state`; Task 3 consumes those exact interfaces; Task 4 consumes Tasks 1–2; Task 5 is gated by Task 4.
