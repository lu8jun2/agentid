# Integration Requirements

## Purpose

This document defines what an external system must provide before its events should materially affect `AgentID` reputation.

The goal is to make integrations useful without weakening trust quality.

## Integration Categories

An integration may connect to `AgentID` in two different ways:

### Category 1: Record-Only Integration

Use when the source mainly wants:

- agent history
- event audit trail
- visibility

This category does not imply strong score effect.

### Category 2: Reputation-Bearing Integration

Use when the source expects its events to materially influence score, ranking, or domain reputation.

This category requires stronger workflow guarantees.

## Minimum Requirements For Record-Only Integration

The source should provide:

- stable source name
- stable event identifiers
- basic payload semantics
- replay-safe write discipline

This is enough to store events, but not enough for strong score trust.

## Minimum Requirements For Reputation-Bearing Integration

The source should provide:

- backend-owned source of truth
- stable task or job identifiers
- role separation
- explicit lifecycle states
- enough metadata to distinguish practice vs paid or low-stakes vs commercial work
- failure and cancellation visibility
- some form of counterparty confirmation or platform verification

Strongly preferred:

- settlement or dispute visibility
- bilateral review support
- deterministic event mapping from workflow states

## Required Questions For Integration Review

Before upgrading an integration beyond record-only, review these questions:

1. Is event generation server-side or client-side?
2. Can the source distinguish commercial work from training work?
3. Are state transitions explicit and finite?
4. Can duplicated or replayed task events be detected?
5. Is there any counterparty acknowledgment?
6. Can disputes, cancellations, or failed outcomes be represented?
7. What source tier should this integration receive?

## Event Mapping Requirement

Every serious integration should provide an explicit mapping table:

| Source state change | AgentID event | Class | Source tier |
|---|---|---|---|
| example: task accepted | `JOB_MATCHED` | A | Tier 1 |
| example: task completed (practice) | `TASK_COMPLETED` | B | Tier 1 |
| example: task completed (paid, settled) | `TASK_COMPLETED` | C | Tier 1 |

Without this mapping, event semantics will drift over time.

## Current Example: AgentWorker

`agentworker` is currently the reference integration because it already provides:

- backend-owned task states
- client vs hunter role distinction
- practice vs paid split
- completion, failure, cancellation, review, and settlement semantics

This makes it a good template for future platform integrations.

## Approval Recommendation

New integrations should be approved progressively:

1. allow record-only mode first
2. observe event quality
3. classify source tier
4. enable low-weight score effect
5. only later allow strong commercial score effect

## Failure Rule

If an integration cannot support the minimum workflow guarantees for reputation-bearing use, it should remain record-only until upgraded.
