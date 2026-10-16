# MODULE PROMOTION GOVERNANCE V1

Status: GOVERNANCE_FROZEN
Applies to: market-regime / fragility / shock / transmission / router / lifecycle / timing research modules
Production change: NONE

## 1. Purpose

Prevent single-day narrative repair, state proliferation, data snooping and silent promotion of research ideas into production logic.

Every module must be evaluated against a locked simple baseline before promotion. A module that cannot define its own falsification criteria is not eligible for promotion.

## 2. Evidence grades

Evidence grade describes the strength of support; it is not the same as module status.

- `E0_CONCEPTUAL`: logic or mechanism only; no empirical test.
- `E1_SINGLE_EPISODE`: one day / one event / one historical episode, including a useful counterexample. Hypothesis-generating only.
- `E2_REPLICATED_RESEARCH`: repeated across multiple independent historical episodes or controls, but windows are already consumed by research and therefore are not formal OOS.
- `E3_PREREG_UNUSED`: evaluated on a preregistered, genuinely unused holdout or prospective shadow window after definitions and baseline were locked.
- `E4_PROSPECTIVE_REPLICATION`: independently repeated prospective evidence across materially different market regimes with implementation parity.

Rules:

1. `E1` can never create a production rule.
2. Reusing a consumed historical window cannot upgrade evidence to `E3`.
3. A post-hoc rule repair resets the revised hypothesis to at most `E1` until independently retested.
4. Evidence grades attach to specific hypotheses, not to the whole architecture by association.
5. A post-hoc state addition / split / merge / precedence change is a rule repair even if no numeric threshold changed.

## 3. Module lifecycle

- `CONCEPTUAL`
- `RESEARCH_ONLY`
- `SHADOW_ONLY`
- `CANDIDATE`
- `PRODUCTION_FROZEN`
- `REJECTED_FOR_PROMOTION`

Promotion is not automatic when evidence grade rises.

## 4. Required module contract before empirical testing

Each module must preregister:

- module name / version / immutable rule hash when executable;
- exact input fields and PIT availability;
- source-group declaration for each input family;
- output state or score;
- state-registry reference when categorical enums are used;
- intended decision consequence;
- explicit non-goals;
- invalidation / falsification conditions;
- missing-data and stale-data behavior;
- implementation status (`UNIMPLEMENTED`, `PARTIAL`, `IMPLEMENTED_SHADOW`, `PRODUCTION`);
- primary evaluation metric;
- secondary metrics;
- evaluation horizon(s);
- benchmark / baseline version;
- sampling unit and episode-independence definition;
- ablation comparator / collapsed-state comparator;
- power / minimum-effect assumptions used to determine required sample size;
- multiple-testing family and correction method where applicable;
- known consumed windows that are prohibited from formal OOS claims.

Until the power / minimum-effect assumptions are frozen, `minimum_sample_required = NOT_FROZEN` and promotion beyond `RESEARCH_ONLY` is prohibited.

## 5. Promotion gates

### CONCEPTUAL -> RESEARCH_ONLY

Required:

- complete module contract;
- auditable data provenance plan;
- at least one falsifiable hypothesis;
- at least one negative-control or failure scenario specified in advance;
- no production dependency.

No performance claim is required.

### RESEARCH_ONLY -> SHADOW_ONLY

Required:

- baseline locked before the next evaluation window;
- primary metric and failure conditions locked;
- positive and negative / false-positive controls examined;
- evidence at least `E2_REPLICATED_RESEARCH`;
- all material contradictions explicitly unresolved or adjudicated;
- execution feasibility and missing-data semantics documented;
- complete state-enum registry for all decision-active categorical states;
- ablation plan locked;
- no threshold or state-space tuning on the intended shadow evaluation set.

Historical replication alone is insufficient for `CANDIDATE`.

### SHADOW_ONLY -> CANDIDATE

Required:

- `E3_PREREG_UNUSED` evidence;
- preregistered sample-size requirement satisfied using the correct effective sampling unit;
- primary endpoint beats the locked simple baseline under the preregistered comparison test;
- confidence interval / uncertainty estimate reported;
- false-alarm cost reported alongside tail-risk benefit;
- removal / collapse ablation demonstrates incremental decision value;
- no material deterioration in execution feasibility, turnover burden, or hard-risk constraints;
- results remain valid after the preregistered multiple-testing correction, if applicable;
- no post-hoc state or threshold change during the evaluation window;
- portfolio hard-risk mandate and action map needed for the claimed economic effect were frozen before the unused set opened.

If the primary endpoint fails, the module cannot be rescued by secondary metrics.

### CANDIDATE -> PRODUCTION_FROZEN

Required:

- `E4_PROSPECTIVE_REPLICATION`;
- implementation parity between shadow and proposed production calculation;
- hard portfolio / execution safeguards implemented independently of the model state;
- numeric portfolio hard-risk mandate frozen and executable;
- reproducible provenance and versioned checkpoint;
- no unresolved data-access dependency masquerading as an implemented feature;
- formal review that added complexity delivers incremental value over both `BASELINE_0` and `BASELINE_1`;
- final ablation confirms that each retained decision-active module materially contributes to the preregistered objective.

Any production rule must have a rollback condition.

## 6. Automatic rejection / reset conditions

Set `REJECTED_FOR_PROMOTION`, or reset the revised hypothesis to `E1`, when any of the following occurs:

- primary endpoint underperforms the locked baseline on the preregistered evaluation set;
- material look-ahead / survivorship / timestamp contamination is discovered;
- a rule is changed after seeing its evaluation outcomes;
- a state is added / split / merged / semantically changed after seeing outcomes without a version reset;
- claimed input is not actually available at decision time;
- implementation cannot reproduce the research state from the same PIT inputs;
- benefit exists only after excluding adverse episodes not excluded ex ante;
- module adds states without measurable incremental decision value;
- ablation shows that removal / state collapse does not materially worsen the preregistered decision objective.

## 7. Multiple testing / researcher degrees of freedom

Default discipline:

1. exactly one primary hypothesis per module version;
2. all other endpoints are secondary / exploratory unless preregistered otherwise;
3. if several primary hypotheses are tested as one family, use Holm correction for family-wise error control;
4. no choosing the best horizon after observing outcomes — primary horizon must be locked first;
5. any exploratory discovery requires a new version and a new unused test window;
6. state-space changes are researcher degrees of freedom and are governed exactly like threshold changes.

## 8. Complexity penalty

Every additional state, branch, field or veto must answer:

`What incremental decision error does this element reduce versus the locked simple baseline and versus the architecture with this element removed?`

If no measurable incremental value can be demonstrated, the element remains descriptive or is removed. State count itself is not evidence of model quality.

`STATE_ENUM_ABLATION_GOVERNANCE_V1.md` is binding for all decision-active state families.

## 9. Current evidence interpretation

The 2026-10-15 same-day examples (e.g. individual stock RS / catalyst / theme-dispersion observations) are `E1_SINGLE_EPISODE` unless separately supported by independent evidence.

The already-consumed historical shock / fragility windows may support `E2_REPLICATED_RESEARCH`, but they cannot be relabeled as formal OOS.

No current new regime/fragility module is eligible for `CANDIDATE` under this governance document.

## 10. Hard gates and soft scores are separate

The architecture must not treat all layers as multiplicative scores.

- `HARD GATES / VETOES`: data validity, execution feasibility, model-independent portfolio limits, fail-closed states and explicitly protective risk restrictions.
- `SOFT EVIDENCE / RANKING`: relative preference among eligible actions.

Satisfying a hard gate never adds positive alpha or risk score. Failing a hard gate can block or cap an action.

Any new multiplicative interaction among soft layers is a new hypothesis requiring versioning, preregistration and ablation.

## 11. Information-family overlap

Several modules may be transformations of the same price / volume information.

Before promotion, the module must declare source groups and must not call them independent evidence solely because they appear in different layers.

At minimum, ablation must compare:

- full architecture;
- simple baseline;
- candidate module removed;
- candidate state family collapsed;
- where practical, all transforms from the same source group removed together.

The purpose is to estimate incremental decision information, not count labels.

## 12. Rare-event modules

Shock / source-persistence / transmission / active-de-risking modules are treated as rare-event risk controls by default.

For these modules:

- effective sample is independent `EVENT_EPISODE` count, not daily session count;
- adjacent days inside one shock do not create independent events;
- quiet prospective time adds uptime evidence but not event-outcome sample size;
- event classification must be based on timestamped contemporaneous evidence available at the decision cutoff;
- retrospective event relabeling cannot support E3;
- default actions may tighten or preserve risk but may not raise leverage / exposure above the non-event policy without a separate validated path.

This prevents rare-event insurance logic from being misrepresented as a high-frequency predictor.

## 13. P0 portfolio-risk mandate

`PORTFOLIO_HARD_RISK_GUARD_V1.md` is a P0 production gate.

Numeric limits are not research parameters and must not be optimized on consumed strategy outcomes. They require one explicit portfolio-risk mandate covering single-name, theme, factor, beta, gross/net, liquidity, gap-risk, loss, drawdown and kill-switch limits.

The hard-risk mandate is upstream of economic minimum-effect justification because `delta_tau` has no economic meaning until the project defines what action / exposure change a risk score causes.
