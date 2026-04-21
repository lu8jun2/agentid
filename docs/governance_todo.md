# AgentID Governance TODO

## Purpose

This document tracks the next implementation steps required to turn the governance rules into actual system behavior.

It is intentionally narrower than the general product roadmap.
It focuses only on:

- event eligibility
- source trust
- score finalization
- integration review requirements

## Current Status

Completed:

- governance foundation written
- event admission policy written
- source tiering policy written
- score finalization policy written
- integration requirements written

Not completed:

- governance rules are not yet fully enforced in code
- scoring still relies on relatively simple event interpretation
- source tier is not yet a first-class scoring input
- settlement-aware finalization is not yet explicit

## Priority 1: Add Governance Metadata To Events

- [ ] Define a stable metadata model for:
  - `source_name`
  - `source_tier`
  - `score_class`
  - `settlement_state`
- [ ] Decide whether this metadata lives:
  - inside event payload
  - inside derived interpretation logic
  - or both
- [ ] Document the minimum required event payload keys for score-bearing integrations

## Priority 2: Introduce Event Interpretation Layer

- [ ] Add a central event interpretation module before score aggregation
- [ ] Convert raw event input into normalized scoring semantics
- [ ] Distinguish:
  - record-only events
  - growth events
  - commercial trust events
- [ ] Ensure unknown events default to conservative treatment

## Priority 3: Make Source Tier Part Of Scoring

- [ ] Add source-tier-aware weighting in the scoring pipeline
- [ ] Keep Tier 1 platform backends highest trust by default
- [ ] Down-rank Tier 2 partial workflow systems
- [ ] Default Tier 3 self-reported sources to low or zero direct score impact
- [ ] Write unit tests for tier-based weighting behavior

## Priority 4: Make Settlement Part Of Score Finalization

- [ ] Define normalized settlement states for scoring purposes
- [ ] Decide which event/state combinations qualify for full commercial score
- [ ] Prevent unresolved dispute states from receiving full reputation credit
- [ ] Distinguish:
  - practice completion
  - paid completion
  - paid completion with bilateral confirmation
  - paid completion with settlement
- [ ] Write unit tests for finalization rules

## Priority 5: Upgrade Integration Review Process

- [ ] Create a lightweight integration review checklist template
- [ ] Require every new integration to declare:
  - source of truth
  - source tier
  - practice vs paid distinction
  - review/dispute/settlement support
- [ ] Default unreviewed integrations to record-only or low-trust mode
- [ ] Treat `agentworker` as the reference Tier 1 integration

## Priority 6: Align Existing Event Types

- [ ] Review `VALID_EVENT_TYPES` against admission classes
- [ ] Review scheduler handling against admission classes
- [ ] Explicitly define how these event types should score:
  - `JOB_POSTED`
  - `JOB_MATCHED`
  - `TASK_COMPLETED`
  - `TASK_FAILED`
  - `PEER_RATING`
  - `KNOWLEDGE_EXCHANGE`
- [ ] Decide which current events are history-only vs score-bearing

## Priority 7: Governance Testing

- [ ] Add unit tests for event admission classification
- [ ] Add unit tests for source tier interpretation
- [ ] Add unit tests for settlement-aware score finalization
- [ ] Add regression tests for practice-event down-weighting after governance refactor

## Recommended Implementation Order

1. Add interpretation layer
2. Add source tier weighting
3. Add settlement-aware finalization
4. Add integration review template
5. Expand tests

## Immediate Next Task

The cleanest next coding step is:

- build a central event interpretation helper used by `agentid/worker/scheduler.py`

That is the point where the governance model starts becoming executable.
