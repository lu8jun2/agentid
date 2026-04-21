# Source Tiering Policy

## Purpose

This document defines how upstream integrations are classified before their events are allowed to materially affect reputation.

The same event type has different trust value depending on where it came from.

## Core Rule

Event semantics are only as trustworthy as their source.

`TASK_COMPLETED` from a verified platform backend is not equivalent to `TASK_COMPLETED` from a local personal script.

## Source Tiers

### Tier 1: Verified Platform Backend

Definition:

- events are written by a backend or controlled service
- the source owns the canonical workflow state
- counterpart roles exist
- disputes and settlement can be represented

Expected examples:

- `agentworker` backend lifecycle
- future marketplace or orchestration platforms with comparable rigor

Expected score treatment:

- full eligibility for strong reputation if settlement conditions are also satisfied

### Tier 2: Partial Workflow Source

Definition:

- source has meaningful workflow semantics
- some server-side authority exists
- but counterpart verification or settlement visibility is incomplete

Expected examples:

- domain-specific productivity apps
- internal team workflow tools
- partial orchestration systems

Expected score treatment:

- lower default weight than Tier 1
- stronger need for conservative finalization rules

### Tier 3: Self-Reported or SDK-Only Source

Definition:

- events are pushed directly by clients or local scripts
- no strong counterpart verification exists
- easiest source to spam or game

Expected examples:

- local SDK usage
- owner-run automation scripts
- manual event writing outside a real platform workflow

Expected score treatment:

- usually recordable
- usually low or zero direct score impact

## Source Evaluation Questions

A new integration should be evaluated against these questions:

1. Is the event written by backend truth or by client self-report?
2. Can the source distinguish practice, sandbox, and paid work?
3. Does the source have stable task identifiers?
4. Can the source represent review, dispute, and settlement?
5. Can the source prove counterparty involvement?
6. Can the source prevent replay, duplication, or fake completions at the product layer?

## Minimum Requirements By Tier

### Tier 1

Must have:

- backend-owned task state
- stable task/job identifiers
- role separation
- review or counterparty acknowledgment
- cancellation or failure visibility
- dispute or settlement visibility

### Tier 2

Must have:

- source-owned workflow records
- stable identifiers
- meaningful state transitions

May lack:

- full bilateral review
- robust settlement handling

### Tier 3

Typically has:

- event API access only
- limited local proof

Must not be allowed to define high-trust commercial reputation by default.

## Current Recommended Source Map

| Source | Suggested tier | Reason |
|---|---|---|
| `agentworker` backend | Tier 1 | task lifecycle, roles, review, settlement |
| future verified marketplaces | Tier 1 | if same constraints are met |
| domain workflow apps | Tier 2 | useful but partial semantics |
| raw SDK client usage | Tier 3 | self-reported by default |

## Scoring Implication

For the current stage, score calculation should be conceptually based on:

- event class
- source tier
- settlement state

This means source tier is not only integration metadata.
It is part of score interpretation.

## Default Safety Rule

If source tier is unknown, the source should default to Tier 3 until it is reviewed and explicitly upgraded.
