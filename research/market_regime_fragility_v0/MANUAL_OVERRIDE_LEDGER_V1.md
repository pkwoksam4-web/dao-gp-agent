# MANUAL OVERRIDE LEDGER V1

Status: GOVERNANCE_FROZEN / EXECUTABLE_VALIDATOR_IMPLEMENTED
Version: `MANUAL_OVERRIDE_LEDGER_V1`
Production change: NONE
Formal OOS authorization: NO

## 1. Purpose

Record every human/manual intervention without rewriting the model's original output. The ledger exists so later analysis can distinguish:

- `MODEL_ONLY`: what the frozen model would have done;
- `AS_OPERATED`: what was actually done after any authorized human override;
- `HUMAN_INCREMENT`: the incremental effect of the override itself.

A manual override is not a model update and does not retroactively change the model state, score, action, evidence grade or rule hash.

## 2. Executable contract

Validator:

`manual_override_ledger_v1.py`

Tests:

`test_manual_override_ledger_v1.py`

The validator emits deterministic SHA256 hashes for both individual override records and the canonical ledger. It always returns `production_authorized = false`; this research validator is not an execution authorization surface.

## 3. Required pre-decision fields

Every override record must include:

- `override_id`: unique immutable identifier;
- `recorded_at`: timezone-aware timestamp;
- `action_cutoff`: timezone-aware cutoff for the affected action;
- `scope_type`: one of `SYMBOL / THEME / PORTFOLIO / MODULE / ORDER`;
- `scope_id`: affected symbol/theme/portfolio/module/order identity;
- `module_version`: frozen model/module version being overridden;
- `model_output_hash`: immutable identity of the original model output;
- `original_action`: model's unmodified action;
- `override_action`: replacement human action;
- `reason_code`: categorical reason;
- `reason_text`: contemporaneous explanation;
- `actor_role`: `USER / PORTFOLIO_MANAGER / RISK_OWNER / AUTHORIZED_OPERATOR`;
- `evidence_refs`: contemporaneous evidence references;
- `production_authorized`: false in this research ledger contract.

The override must be recorded no later than the action cutoff. A post-hoc explanation recorded after the cutoff cannot be represented as a valid pre-decision override record.

## 4. Immutability rule

The model output is append-only evidence.

An override record may point to the model output but may never replace, delete or mutate:

- model score/state;
- model action;
- model rule/config hash;
- model evidence ledger;
- model timestamp.

The model's original output remains the source for primary model-performance evaluation.

## 5. No future-outcome contamination

Pre-decision override records must not contain realized or future outcome fields.

Fields such as the following are forbidden in the pre-decision record:

- `future_*`;
- `forward_*`;
- `outcome_*`;
- `post_action_*`;
- `realized_pnl`;
- realized win/hit-rate fields.

Outcome evaluation, when mature, is appended in a separate evaluation artifact keyed by `override_id` and cannot alter the original record hash.

## 6. Primary versus secondary evaluation

Formal model evaluation must use **unoverridden model outputs** for the primary model metric.

If manual overrides occurred, report separately:

1. `MODEL_ONLY` — frozen model action/output versus outcome;
2. `AS_OPERATED` — actual operated action after override versus outcome;
3. `HUMAN_INCREMENT = AS_OPERATED - MODEL_ONLY` under the preregistered economic metric where such a metric is defined.

A human-assisted result cannot be presented as proof that the underlying model predicted correctly.

Likewise, a model miss corrected by a human must remain a model miss in the model-only ledger.

## 7. Override-count semantics

Every formal/shadow evaluation manifest must carry:

- `manual_override_count`;
- `manual_override_ledger_hash`.

The ledger hash is required even when count is zero. An empty ledger therefore has a deterministic identity rather than being represented by missing provenance.

If `manual_override_count > 0`, all override records must validate and the count must match the canonical ledger.

A future integration layer may bind the manifest directly to the canonical ledger count/hash; until that adapter exists, the preflight contract only verifies that the required provenance fields are present and correctly typed.

## 8. Reason taxonomy

The validator intentionally does not freeze a detailed reason-code enum beyond requiring a non-empty code, because the operational taxonomy has not yet been independently designed.

Examples of future categories may include execution impossibility, hard-risk intervention, data-quality concern, compliance restriction or discretionary risk judgment, but no category is promoted here by example alone.

Adding a reason taxonomy that changes decision authority or automatic action semantics is a governance/version change.

## 9. Interaction with downgrade/change control

`MODULE_DOWNGRADE_CHANGE_CONTROL_V1` is binding.

A manual override is not permission to modify frozen model logic. Repeated overrides may motivate a new research hypothesis, but any subsequent rule change must:

- be separately versioned;
- treat the override/outcome window as consumed;
- reset evidence as required by promotion governance;
- use a new genuinely unused evaluation window before formal promotion.

A manual intervention that silently changes a frozen rule or output without a ledger entry is itself an integrity breach and may trigger `QUARANTINED` under change control.

## 10. Current limitations

Not yet frozen:

- detailed manual-override reason-code taxonomy;
- authorized actor identities/account mapping;
- economic `HUMAN_INCREMENT` metric, because the risk-score -> action/exposure map remains unfrozen;
- automatic production execution of an override.

This contract freezes auditability and attribution, not discretionary trading authority.
