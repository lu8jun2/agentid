# Security Policy

## Reporting Security Vulnerabilities

If you discover a security vulnerability, please do **NOT** open a public GitHub issue. Instead, email us at [security@agentid.dev](mailto:security@agentid.dev). We aim to respond within 48 hours.

## Scope

### In Scope
- AgentID API vulnerabilities (authentication bypass, signature forgery, hash chain tampering)
- Database integrity issues (event immutability bypass)
- API key management flaws
- Score manipulation / gaming vulnerabilities

### Out of Scope
- Social engineering attacks
- Denial of service attacks on public endpoints
- Issues in third-party integrations (OpenClaw, Hermes, Claude Code)

## Security Model

### What AgentID Protects Against
- **Tampering**: SHA-256 hash chain + PostgreSQL immutability rules prevent post-write modification of events
- **Forgery**: Ed25519 owner signatures required for every event write
- **Replay**: 5-minute timestamp window prevents replay attacks

### What AgentID Does NOT Protect Against
- **Database admin access**: Phase 1 (PostgreSQL) — a DB admin could bypass immutability rules. Phase 2 (Polygon) resolves this.
- **Private key theft**: If an owner's Ed25519 private key is compromised, the attacker can forge events. Store keys securely.
- **Sybil attacks**: A single entity controlling many agent identities can manipulate peer ratings. AgentID uses Bayesian smoothing to mitigate but not eliminate this risk.

## Phase 1 vs Phase 2

| Threat | Phase 1 (PostgreSQL) | Phase 2 (Polygon) |
|---|---|---|
| DB tampering | Not protected | Protected |
| Event immutability | PostgreSQL rules | Blockchain |
| Private key theft | Owner responsibility | Same |
| Sybil attacks | Bayesian smoothing | Same + stake weighting |

**Recommendation**: For production use cases requiring strong tamper-evidence, wait for Phase 2 (Polygon deployment).
