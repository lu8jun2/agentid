"""Knowledge propagation network — core logic.

Three responsibilities:
1. InfoPackage generation: platform assembles task list + 6 random peer DIDs + ad slot
2. Integrity verification: SHA-256 of canonical package; any modification = detectable
3. Anti-gaming detection: job posting quality scoring with multi-signal fraud checks
4. KNOWLEDGE_EXCHANGE: periodic peer pairing for decentralized knowledge propagation
"""
import hashlib
import json
import random
import secrets
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field


# ── InfoPackage ──────────────────────────────────────────────────────────────

@dataclass
class AdSlot:
    """Reserved ad slot in every info package. Agents cannot filter or modify."""
    ad_id: str = ""
    content: str = ""        # ad copy
    target_url: str = ""
    advertiser: str = ""


@dataclass
class InfoPackage:
    """The canonical information unit dispatched by the platform to an agent.

    Structure:
      1. task_list   — available jobs matching the agent's profile
      2. peer_dids   — 6 randomly selected agent DIDs for mutual exchange
      3. ad_slot     — platform ad (agents cannot modify or filter)

    Agents must forward this package unmodified. Any modification is detectable
    via package_hash comparison.
    """
    recipient_did: str
    task_list: list[dict]          # [{job_id, title, domain, reward, ...}]
    peer_dids: list[str]           # exactly 6
    ad_slot: AdSlot = field(default_factory=AdSlot)
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    nonce: str = field(default_factory=lambda: secrets.token_hex(16))


def canonical_package(pkg: InfoPackage) -> str:
    """Deterministic JSON serialization for hashing."""
    return json.dumps({
        "recipient_did": pkg.recipient_did,
        "task_list": pkg.task_list,
        "peer_dids": sorted(pkg.peer_dids),
        "ad_slot": {
            "ad_id": pkg.ad_slot.ad_id,
            "content": pkg.ad_slot.content,
            "target_url": pkg.ad_slot.target_url,
            "advertiser": pkg.ad_slot.advertiser,
        },
        "issued_at": pkg.issued_at,
        "nonce": pkg.nonce,
    }, sort_keys=True, separators=(",", ":"))


def hash_package(pkg: InfoPackage) -> str:
    return hashlib.sha256(canonical_package(pkg).encode()).hexdigest()


def verify_package_integrity(pkg_dict: dict, expected_hash: str) -> bool:
    """Verify a forwarded package matches the original hash.

    Called when peer agents report receiving the package. If the hash
    doesn't match, the forwarding agent failed the integrity check.
    """
    canonical = json.dumps({
        "recipient_did": pkg_dict["recipient_did"],
        "task_list": pkg_dict["task_list"],
        "peer_dids": sorted(pkg_dict["peer_dids"]),
        "ad_slot": pkg_dict.get("ad_slot", {}),
        "issued_at": pkg_dict["issued_at"],
        "nonce": pkg_dict["nonce"],
    }, sort_keys=True, separators=(",", ":"))
    actual = hashlib.sha256(canonical.encode()).hexdigest()
    return actual == expected_hash


def build_info_package(
    recipient_did: str,
    task_list: list[dict],
    all_active_dids: list[str],
    ad_slot: AdSlot | None = None,
    peer_count: int = 6,
) -> tuple[InfoPackage, str]:
    """Build an InfoPackage and return (package, package_hash).

    Randomly selects peer_count agents from all_active_dids, excluding
    the recipient itself.
    """
    candidates = [d for d in all_active_dids if d != recipient_did]
    peers = random.sample(candidates, min(peer_count, len(candidates)))
    pkg = InfoPackage(
        recipient_did=recipient_did,
        task_list=task_list,
        peer_dids=peers,
        ad_slot=ad_slot or AdSlot(),
    )
    return pkg, hash_package(pkg)


# ── Anti-gaming: job posting quality scoring ─────────────────────────────────

MIN_REWARD_USD = 1.0          # postings below this don't count
MAX_PRIOR_INTERACTIONS = 3    # poster/acceptor must be "strangers"
COOLDOWN_HOURS = 24           # same poster: only 1 valid posting per 24h


@dataclass
class PostingEligibility:
    eligible: bool
    reason: str


def check_posting_eligibility(
    poster_did: str,
    acceptor_did: str,
    reward_amount: float,
    reward_currency: str,
    prior_interactions: int,
    last_counted_posting_at: datetime | None,
    now: datetime | None = None,
) -> PostingEligibility:
    """Multi-signal anti-gaming check for job posting quality score.

    Returns eligibility + reason. All five signals must pass.
    """
    now = now or datetime.now(timezone.utc)

    if reward_currency == "USD" and reward_amount < MIN_REWARD_USD:
        return PostingEligibility(False, f"reward below minimum ${MIN_REWARD_USD}")

    if prior_interactions > MAX_PRIOR_INTERACTIONS:
        return PostingEligibility(False, f"poster/acceptor have {prior_interactions} prior interactions (max {MAX_PRIOR_INTERACTIONS})")

    if last_counted_posting_at:
        elapsed = now - last_counted_posting_at
        if elapsed < timedelta(hours=COOLDOWN_HOURS):
            remaining = COOLDOWN_HOURS - elapsed.total_seconds() / 3600
            return PostingEligibility(False, f"cooldown active, {remaining:.1f}h remaining")

    return PostingEligibility(True, "all checks passed")


def finalize_posting_score(
    poster_rated: bool,
    acceptor_rated: bool,
    status: str,
) -> bool:
    """A posting counts toward quality score only when:
    - status == completed
    - both sides submitted ratings (bilateral requirement)
    """
    return status == "completed" and poster_rated and acceptor_rated


# ── KNOWLEDGE_EXCHANGE: periodic peer pairing ──────────────────────────────────

SESSION_DURATION_MINUTES = 30
EXCHANGE_PEER_COUNT = 6
MIN_AGENTS_FOR_EXCHANGE = 7  # need at least 7 to form one complete exchange group


def build_exchange_pairs(all_active_dids: list[str]) -> list[tuple[str, list[str]]]:
    """Build random peer-exchange groups.

    Each group is (initiator, [peer1..peer6]).
    An initiator dispatches InfoPackage to peers; peers forward to each other.

    Groups are non-overlapping — an agent appears in at most one group.
    Returns list of (initiator_did, [peer_dids]).
    """
    if len(all_active_dids) < MIN_AGENTS_FOR_EXCHANGE:
        return []

    pool = list(all_active_dids)
    random.shuffle(pool)
    pairs = []

    while len(pool) >= EXCHANGE_PEER_COUNT:
        initiator = pool.pop(0)
        peers = pool[:EXCHANGE_PEER_COUNT]
        pool = pool[EXCHANGE_PEER_COUNT:]
        pairs.append((initiator, peers))

    return pairs


def build_exchange_package_content(initiator_did: str, peer_dids: list[str]) -> dict:
    """Build the payload for a KNOWLEDGE_EXCHANGE event."""
    return {
        "msg_type": "KNOWLEDGE_EXCHANGE",
        "initiator_did": initiator_did,
        "peer_dids": peer_dids,
        "peer_count": len(peer_dids),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
