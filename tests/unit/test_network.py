"""Unit tests for knowledge propagation network core logic."""
import pytest
from datetime import datetime, timedelta, timezone
from agentid.core.network import (
    build_info_package, hash_package, verify_package_integrity,
    canonical_package, AdSlot, InfoPackage,
    check_posting_eligibility, finalize_posting_score,
)


ALL_DIDS = [f"did:agentid:local:agent{i}" for i in range(20)]
RECIPIENT = ALL_DIDS[0]


def test_build_package_selects_6_peers():
    pkg, pkg_hash = build_info_package(RECIPIENT, [], ALL_DIDS)
    assert len(pkg.peer_dids) == 6
    assert RECIPIENT not in pkg.peer_dids
    assert len(pkg_hash) == 64


def test_package_hash_deterministic():
    pkg = InfoPackage(
        recipient_did=RECIPIENT,
        task_list=[{"job_id": "j1"}],
        peer_dids=ALL_DIDS[1:7],
        ad_slot=AdSlot(),
        issued_at="2026-04-19T00:00:00",
        nonce="abc123",
    )
    h1 = hash_package(pkg)
    h2 = hash_package(pkg)
    assert h1 == h2


def test_integrity_verification_passes_unmodified():
    pkg, pkg_hash = build_info_package(RECIPIENT, [{"job_id": "j1"}], ALL_DIDS)
    pkg_dict = {
        "recipient_did": pkg.recipient_did,
        "task_list": pkg.task_list,
        "peer_dids": pkg.peer_dids,
        "ad_slot": {"ad_id": "", "content": "", "target_url": "", "advertiser": ""},
        "issued_at": pkg.issued_at,
        "nonce": pkg.nonce,
    }
    assert verify_package_integrity(pkg_dict, pkg_hash)


def test_integrity_verification_fails_on_modification():
    pkg, pkg_hash = build_info_package(RECIPIENT, [{"job_id": "j1"}], ALL_DIDS)
    pkg_dict = {
        "recipient_did": pkg.recipient_did,
        "task_list": [{"job_id": "j1"}, {"job_id": "injected"}],  # tampered
        "peer_dids": pkg.peer_dids,
        "ad_slot": {"ad_id": "", "content": "", "target_url": "", "advertiser": ""},
        "issued_at": pkg.issued_at,
        "nonce": pkg.nonce,
    }
    assert not verify_package_integrity(pkg_dict, pkg_hash)


def test_posting_eligibility_passes():
    result = check_posting_eligibility(
        poster_did="did:a", acceptor_did="did:b",
        reward_amount=10.0, reward_currency="USD",
        prior_interactions=1,
        last_counted_posting_at=None,
    )
    assert result.eligible


def test_posting_eligibility_fails_low_reward():
    result = check_posting_eligibility(
        poster_did="did:a", acceptor_did="did:b",
        reward_amount=0.5, reward_currency="USD",
        prior_interactions=0,
        last_counted_posting_at=None,
    )
    assert not result.eligible
    assert "minimum" in result.reason


def test_posting_eligibility_fails_too_many_interactions():
    result = check_posting_eligibility(
        poster_did="did:a", acceptor_did="did:b",
        reward_amount=10.0, reward_currency="USD",
        prior_interactions=5,
        last_counted_posting_at=None,
    )
    assert not result.eligible
    assert "prior interactions" in result.reason


def test_posting_eligibility_fails_cooldown():
    recent = datetime.now(timezone.utc) - timedelta(hours=2)
    result = check_posting_eligibility(
        poster_did="did:a", acceptor_did="did:b",
        reward_amount=10.0, reward_currency="USD",
        prior_interactions=0,
        last_counted_posting_at=recent,
    )
    assert not result.eligible
    assert "cooldown" in result.reason


def test_finalize_posting_score_requires_bilateral():
    assert not finalize_posting_score(True, False, "completed")
    assert not finalize_posting_score(False, True, "completed")
    assert not finalize_posting_score(True, True, "matched")
    assert finalize_posting_score(True, True, "completed")
