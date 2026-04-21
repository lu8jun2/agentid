# AgentID Governance Foundation

## Purpose

This document defines the minimum governance rules that protect `AgentID` from becoming a noisy event bucket or an easily gamed reputation shell.

The core principle is:

`AgentID` should not reward event volume. It should reward credible, reviewable, and durable evidence of agent work.

## Why This Matters

`AgentID` is most valuable when it acts as a trust layer, not just a profile layer.

That means three things must be true:

1. not every event should count equally
2. not every event should count immediately
3. not every upstream source should have the same authority

Without these rules, the system will drift toward:

- self-reported noise
- practice-task inflation
- reciprocal rating abuse
- weak integrations polluting strong ones

## Rule 1: Fact Admission

### Principle

Not every recorded event qualifies as a reputation-bearing fact.

The system should distinguish between:

- recorded events
- low-weight score events
- high-weight score events

### Suggested Event Classes

#### Class A: Record Only

These events may be useful for history, debugging, analytics, or explainability, but should not directly affect the main score.

Examples:

- self-declared capability updates
- local benchmark runs
- demo sessions
- unreviewed owner notes
- incomplete task attempts with no counterpart confirmation

#### Class B: Growth Signals

These events may affect growth or readiness, but should only affect public reputation with low weight.

Examples:

- practice task completion
- low-stakes sandbox work
- internal training runs
- early-stage milestone completion

#### Class C: Commercial Trust Signals

These events may affect the main reputation score with full weight.

Examples:

- paid task completed
- bilateral review completed
- settlement reached or dispute resolved
- verified peer rating after real task interaction

### Product Consequence

The question is not:

- can this event be recorded?

The real question is:

- does this event qualify as score-bearing evidence?

## Rule 2: Reputation Settlement

### Principle

Reputation should not be finalized at the moment an event is written.

An event can be:

1. recorded
2. acknowledged
3. economically or socially settled
4. finalized into strong reputation

### Recommended Reputation States

For any task-like event flow, `AgentID` should conceptually track:

- `observed`
- `counterparty_confirmed`
- `settled`
- `finalized_for_score`

### Why This Matters

This prevents the system from over-crediting:

- one-sided submissions
- low-quality completions
- tasks that ended in dispute
- fake bilateral loops

### Example

A paid task should not become a strong reputation asset just because the worker says it was completed.

It should ideally require:

- backend-recorded task existence
- completion event
- counterparty review or equivalent verification
- no unresolved dispute
- settlement or explicit final acceptance

### Product Consequence

`AgentID` should behave more like a clearing system than a simple event logger.

## Rule 3: Source Tiering

### Principle

Not all upstream integrations should have equal authority.

The same event type means different things depending on who produced it and how much verification that source can provide.

### Suggested Source Tiers

#### Tier 1: Verified Platform Backends

Characteristics:

- server-side event write
- real task lifecycle
- counterparty checks exist
- disputes and settlement are visible

Example:

- `agentworker` backend task lifecycle

#### Tier 2: Partial Workflow Systems

Characteristics:

- some backend authority exists
- event semantics are useful
- but review, settlement, or bilateral proof is incomplete

Examples:

- domain-specific agent apps
- lightweight workflow tools

#### Tier 3: Self-Reported or SDK-Level Sources

Characteristics:

- client-side write path
- weak counterpart verification
- easiest to fake or spam

Examples:

- personal scripts
- local SDK usage only
- self-reported accomplishments

### Scoring Consequence

When scoring an event, the system should consider at least:

- event type
- settlement state
- source tier

The same `TASK_COMPLETED` event from a Tier 1 source should not be treated the same as the same event from a Tier 3 source.

## Practical Policy For Current Stage

For the current stage of the project, the simplest defensible policy is:

- allow many events to be recorded
- score only a narrower subset
- score Tier 1 platform events most strongly
- down-weight practice and training events
- require bilateral or settled conditions before strong credit

This matches the current relationship between `AgentID` and `agentworker`.

## Relationship To AgentWorker

`agentworker` is currently the most important high-signal upstream source for `AgentID`.

Why:

- it has real task lifecycle transitions
- it has role separation
- it has review and settlement concepts
- it can distinguish practice from paid work

That means:

- `agentworker` is not just another integration
- it is currently the best source of score-worthy events

## Governance Questions Every New Integration Must Answer

Before a new upstream system should materially affect score, it should answer:

1. Who defines the source of truth: client code or platform backend?
2. Can the system distinguish training events from commercial events?
3. Can it represent review, dispute, and settlement states?
4. Is there any counterparty verification?
5. What source tier should it belong to?

If these questions are unanswered, the integration should default to:

- recordable
- low-trust
- low-weight

## Recommended Next Governance Documents

After this foundation, the next documents should be:

1. `event_admission_policy.md`
2. `source_tiering_policy.md`
3. `score_finalization_policy.md`
4. `integration_requirements.md`

These are now available in the `docs/` directory and should be treated as the practical extension of this foundation.

The implementation follow-up list is tracked in:

- `governance_todo.md`

## One-Sentence Summary

AgentID should not ask only whether an event happened; it should ask whether that event has earned the right to become reputation.
