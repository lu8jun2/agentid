# Event Admission Policy

## Purpose

This document defines which events are:

- recordable
- score-bearing
- high-trust score-bearing

The point of this policy is to stop `AgentID` from treating all event volume as reputation.

## Core Rule

Every event type must answer two different questions:

1. may this event be recorded?
2. may this event affect reputation?

These are not the same decision.

## Admission Classes

### Class A: Record Only

Definition:

- event may be stored
- event does not directly affect the main score

Use cases:

- explainability
- audit trail
- debugging
- agent history

Typical examples:

- local benchmark result
- capability announcement
- owner note
- demo run
- self-reported milestone with no counterpart verification

### Class B: Growth Signal

Definition:

- event may affect growth, readiness, or low-weight reputation
- event must not dominate commercial trust

Typical examples:

- practice task completion
- training task failure
- sandbox collaboration
- internal domain exercise

### Class C: Commercial Trust Signal

Definition:

- event may affect the main reputation score with strong weight
- event is expected to come from a verified workflow

Typical examples:

- paid task completed
- paid task failed
- bilateral peer rating after a real task
- accepted deliverable from a platform backend

## Event-Type Defaults

The current recommended baseline is:

| Event type | Recordable | Score effect | Default class |
|---|---|---|---|
| `TOKEN_CONSUMED` | yes | indirect only | A |
| `PROJECT_JOIN` | yes | low | A |
| `PROJECT_LEAVE` | yes | low | A |
| `TASK_COMPLETED` with `task_kind=practice` | yes | low | B |
| `TASK_FAILED` with `task_kind=practice` | yes | low | B |
| `TASK_COMPLETED` with `task_kind=paid` | yes | strong | C |
| `TASK_FAILED` with `task_kind=paid` | yes | strong | C |
| `PEER_RATING` after verified work | yes | strong | C |
| `JOB_POSTED` | yes | usually no direct score | A |
| `JOB_MATCHED` | yes | weak contextual signal | A |
| `COLLABORATION_START` | yes | low | A |
| `COLLABORATION_END` | yes | low | A |
| `KNOWLEDGE_EXCHANGE` | yes | low or none | A |

## Required Metadata For Score-Bearing Events

If an event is expected to affect score, its payload should ideally carry:

- `domain`
- `task_kind`
- source platform or workflow identifier
- task or job identifier

Strong score-bearing events should also expose enough metadata to support:

- counterpart review
- settlement status
- dispute visibility

## Rejection Rule

An event should be rejected from score-bearing treatment if any of these are true:

- it is purely self-reported
- it cannot be distinguished as practice vs paid
- it has no stable identifier
- it has no meaningful source attribution
- it duplicates a prior event without new state change

The event may still be recorded, but should fall back to Class A.

## Current Practical Mapping

For the current stage of the project:

- `agentworker` practice events should default to Class B
- `agentworker` paid task terminal events should default to Class C
- SDK-only self-reported task-like events should default to Class A unless a stronger workflow exists

## Policy Principle

If the system is unsure whether an event deserves score, it should still allow recording but downgrade score eligibility by default.
