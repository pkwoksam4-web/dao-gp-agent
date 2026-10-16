# STATE ENUMERATION & ABLATION GOVERNANCE V1

Status: GOVERNANCE_FROZEN
Applies to: market-regime / fragility / shock / transmission / lifecycle / tactical-timing / router state families
Production use: GOVERNANCE_ONLY
Formal OOS: NO

## 1. Purpose

Control model degrees of freedom created by state proliferation.

Adding a state, splitting a state, changing precedence, adding a veto, or changing the semantic boundary of an existing state is a model change even when no numeric threshold changes.

The architecture may not claim that several labels are independent evidence merely because they are represented as separate layers.

## 2. What counts as a state-space change

Any of the following requires a new versioned registry entry:

- add a state;
- remove a state;
- split one state into multiple states;
- merge states;
- rename a state when semantics change;
- change transition semantics;
- change precedence / conflict resolution;
- add or remove a veto;
- change the decision consequence attached to a state;
- move evidence from descriptive to decision-active use.

A purely cosmetic rename with identical semantics and hash-preserving migration may be documented without resetting the hypothesis.

## 3. Mandatory registry fields

Before a new or changed state is used in any empirical evaluation, record:

- `state_family`
- `state_name`
- `state_family_version`
- `registered_at`
- `registered_before_outcome_review = true|false`
- exact semantic definition
- exact atomic inputs / evidence channels
- provenance / PIT requirements
- decision consequence
- sampling unit (`SESSION`, `EVENT_EPISODE`, or another preregistered unit)
- expected rarity class
- baseline / collapsed-state comparator
- ablation comparator
- consumed historical windows
- current evidence grade
- falsification condition
- missing-data behavior

No registry entry means the state is descriptive only and cannot affect position, veto, ranking, promotion, or evaluation.

## 4. Post-hoc state repair rule

If a state or transition is added, split, merged, or semantically changed after observing an outcome that motivated the change:

- increment the affected state-family version;
- label the revised hypothesis `POST_HOC_REPAIR`;
- reset the affected hypothesis to at most `E1_SINGLE_EPISODE`;
- prohibit use of the motivating window as E3 / formal OOS evidence;
- require a new unused / prospective evaluation window before promotion.

This rule applies even when no numeric threshold was tuned.

## 5. Evidence independence rule

Separate labels do not imply separate information.

Price, returns, realized volatility, breadth, leadership, lifecycle, relative strength, turnover and tactical timing may share the same underlying market observations.

Before promotion, each decision-active module must declare its source groups, for example:

- `PRICE_RETURN`
- `VOLUME_TURNOVER`
- `BREADTH_CROSS_SECTION`
- `EVENT_NEWS`
- `DERIVATIVES`
- `FUNDAMENTAL_CATALYST`
- `VENDOR_FLOW`

Multiple transformations from one source group count as one information family for independence claims unless incremental information is demonstrated.

No phrase such as `multiple independent signals` is permitted solely because several derived fields agree.

## 6. Mandatory ablation design

Before a module or state family may advance to `CANDIDATE`, evaluate at minimum:

1. full architecture;
2. locked simple baseline;
3. architecture with the entire candidate module removed;
4. architecture with the candidate state family collapsed to its simpler parent representation where possible.

The ablation report must include, under the same PIT and execution assumptions:

- primary metric change;
- uncertainty interval;
- false-alarm cost;
- tail-risk benefit;
- decision turnover / action count;
- state flip count;
- missing-data rate;
- execution-block rate where applicable;
- economic action impact if the module changes exposure.

If removal or state collapse does not materially worsen the preregistered decision objective, the extra complexity is not justified and remains descriptive or is removed.

## 7. Hard-gate versus score separation

Decision logic must distinguish:

### Hard gates / vetoes

Used only for eligibility, exposure ceilings, execution feasibility, model-independent risk protection, or fail-closed handling.

Hard gates do not add positive score merely because they are satisfied.

### Soft evidence / scores

Used for ranking or relative preference after all mandatory hard gates are satisfied.

The architecture must not multiply many noisy layer scores together by default. A new multiplicative interaction is itself a separately registered hypothesis and requires ablation.

## 8. Rare-event state families

Shock, source-persistence, local-transmission and active-de-risking states are rare-event modules.

For these families:

- the primary sampling unit is an independently defined `EVENT_EPISODE`, not trading days;
- adjacent sessions inside the same shock episode do not count as independent events;
- prospective shadow time with no new event adds operational uptime evidence but does not add event-outcome sample size;
- event labels must be created from timestamped contemporaneous evidence available at the decision cutoff;
- retrospective event relabeling cannot support E3;
- default decision consequence is asymmetric: these modules may tighten or preserve risk limits, but may not increase leverage / exposure above the non-event policy without a separately validated promotion path.

This treats rare-event logic as risk insurance first, not as a high-frequency predictor.

## 9. Freeze point for E3

Before opening any E3 unused / prospective evaluation window, freeze:

- the complete state registry;
- all transition semantics;
- all precedence / conflict rules;
- all veto semantics;
- module decision consequences;
- primary metric and horizon;
- ablation plan.

No state-space expansion is allowed during that evaluation window. A necessary change closes the current version and starts a new version at E1/E2 as applicable.

## 10. Promotion blocker

A module is not eligible for `CANDIDATE` if any of the following is true:

- a decision-active state lacks a registry entry;
- a state was added after outcome review without version reset;
- source-group overlap is described as independent evidence without ablation;
- the module has no measurable decision consequence;
- the module has no removal / collapse ablation;
- a rare-event module counts sessions rather than independent event episodes as its effective sample;
- a new state only improves secondary endpoints after the primary endpoint failed.

## 11. Current interpretation

Existing regime / shock / lifecycle / timing enumerations remain research state families. This governance document does not upgrade their evidence grade.

Any future state addition or split is frozen by this governance rule before it can affect evaluation or downstream portfolio decisions.
