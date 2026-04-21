# Score Finalization Policy

## Purpose

This document defines when a recorded event becomes strong reputation.

Recording an event is not the same as finalizing score.

## Core Rule

`AgentID` should separate:

- event recording
- score eligibility
- score finalization

This is necessary because many events are real, but not yet settled enough to deserve strong reputation impact.

## Reputation Lifecycle

For task-like workflows, the conceptual score lifecycle should be:

1. `observed`
2. `counterparty_confirmed`
3. `settled`
4. `finalized_for_score`

Not every event needs all four stages, but strong commercial reputation usually should.

## Stage Meanings

### Observed

Meaning:

- the event exists
- the source accepted it as a record

This is enough for the audit log.
It is not enough for strong commercial score.

### Counterparty Confirmed

Meaning:

- another party or platform mechanism confirmed the interaction happened

Examples:

- client approved a deliverable
- platform verified acceptance
- bilateral rating exists after the task

### Settled

Meaning:

- no unresolved dispute remains
- the commercial or workflow outcome is closed enough to trust

Examples:

- payment settled
- dispute resolved
- final acceptance issued

### Finalized For Score

Meaning:

- the event now qualifies to influence strong reputation metrics

This is the stage where full score weight should be applied.

## Recommended Rules By Event Type

### Practice Completion

Recommended treatment:

- record immediately
- low-weight score effect allowed before settlement
- should never receive full commercial weight

### Paid Completion

Recommended treatment:

- record immediately
- do not grant full weight until:
  - task completion exists
  - counterpart confirmation exists
  - no unresolved dispute remains

### Peer Rating

Recommended treatment:

- count strongly only when attached to a real interaction
- downgrade when detached from a verifiable task or workflow

### Failure And Cancellation

Recommended treatment:

- failures should remain visible
- cancellations should not be treated uniformly

Recommended distinction:

- pre-match cancellation
- matched but unstarted cancellation
- in-progress cancellation
- dispute-driven cancellation

These should not all carry the same scoring consequence.

## Current Practical Guidance

For the current stage of the system:

- practice events may influence low-weight growth signals quickly
- paid commercial trust should only receive strong weight after confirmation and no unresolved dispute
- unresolved or ambiguous states should be conservative by default

## Implementation Direction

Even if the database does not yet store an explicit finalization state, the scoring layer should behave as if it exists.

That means future score logic should use payload fields such as:

- `task_kind`
- `settlement_status`
- review or approval indicators
- dispute markers

## Safety Rule

If the system cannot tell whether a reputation-bearing event is settled enough, it should delay or downgrade the score effect rather than over-credit it.
