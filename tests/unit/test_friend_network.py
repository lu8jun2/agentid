"""Unit tests for friend network logic."""
import pytest
from datetime import datetime
from agentid.core.friend_network import (
    MAX_FRIENDS, INITIAL_BATCH, BATCH_SIZE, FRIEND_COUNT_THRESHOLD,
    select_friends_for_broadcast, next_batch_size, can_add_friends,
    select_new_friend_candidates, build_id_broadcast_content,
    build_project_broadcast_content, should_deliver_to_owner,
)


class TestSelectFriendsForBroadcast:
    def test_fewer_than_6_friends_returns_empty(self):
        assert select_friends_for_broadcast(["did1", "did2"], {}) == []

    def test_6_to_19_friends_uses_6_fanout(self):
        dids = [f"did{i}" for i in range(6)]
        result = select_friends_for_broadcast(dids, {})
        assert len(result) == 6

    def test_20_plus_friends_uses_3_fanout(self):
        dids = [f"did{i}" for i in range(25)]
        result = select_friends_for_broadcast(dids, {})
        assert len(result) == 3

    def test_exactly_20_friends_uses_3_fanout(self):
        dids = [f"did{i}" for i in range(20)]
        result = select_friends_for_broadcast(dids, {})
        assert len(result) == 3

    def test_exactly_19_friends_uses_6_fanout(self):
        dids = [f"did{i}" for i in range(19)]
        result = select_friends_for_broadcast(dids, {})
        assert len(result) == 6

    def test_result_is_subset_of_input(self):
        dids = [f"did{i}" for i in range(10)]
        result = select_friends_for_broadcast(dids, {})
        assert all(r in dids for r in result)


class TestNextBatchSize:
    def test_zero_friends_returns_6(self):
        assert next_batch_size(0) == 6

    def test_6_friends_returns_6(self):
        assert next_batch_size(6) == 6

    def test_195_friends_returns_5(self):
        assert next_batch_size(195) == 5

    def test_200_friends_returns_0(self):
        assert next_batch_size(200) == 0

    def test_201_friends_returns_0(self):
        assert next_batch_size(201) == 0


class TestCanAddFriends:
    def test_0_friends_can_add(self):
        assert can_add_friends(0) is True

    def test_199_friends_can_add(self):
        assert can_add_friends(199) is True

    def test_200_friends_cannot_add(self):
        assert can_add_friends(200) is False

    def test_250_friends_cannot_add(self):
        assert can_add_friends(250) is False


class TestSelectNewFriendCandidates:
    def test_excludes_self(self):
        all_dids = ["self", "peer1", "peer2"]
        result = select_new_friend_candidates(all_dids, [], "self")
        assert "self" not in result

    def test_excludes_existing_friends(self):
        all_dids = ["agent", "friend1", "friend2", "new1"]
        result = select_new_friend_candidates(all_dids, ["friend1"], "agent")
        assert "friend1" not in result

    def test_respects_max_limit(self):
        all_dids = [f"did{i}" for i in range(50)]
        result = select_new_friend_candidates(all_dids, [], "did0")
        assert len(result) == BATCH_SIZE


class TestBuildIdBroadcastContent:
    def test_includes_did_and_type(self):
        content = build_id_broadcast_content("did:agentid:x", "TestBot", "claude_code", 8.5)
        assert content["msg_type"] == "ID_ADVERTISEMENT"
        assert content["sender_did"] == "did:agentid:x"
        assert content["sender_name"] == "TestBot"
        assert content["sender_type"] == "claude_code"
        assert content["score"] == 8.5
        assert "timestamp" in content


class TestBuildProjectBroadcastContent:
    def test_includes_all_project_fields(self):
        content = build_project_broadcast_content(
            "proj-1", "Build Dashboard", "coding", 50.0, "poster-did", "sender-did"
        )
        assert content["msg_type"] == "PROJECT_BROADCAST"
        assert content["project_id"] == "proj-1"
        assert content["project_title"] == "Build Dashboard"
        assert content["domain"] == "coding"
        assert content["reward_usd"] == 50.0
        assert content["poster_did"] == "poster-did"
        assert content["sender_did"] == "sender-did"


class TestShouldDeliverToOwner:
    def test_id_always_delivered(self):
        assert should_deliver_to_owner("ID_ADVERTISEMENT", False) is True
        assert should_deliver_to_owner("ID_ADVERTISEMENT", True) is True

    def test_project_requires_authorization(self):
        assert should_deliver_to_owner("PROJECT_BROADCAST", False) is False
        assert should_deliver_to_owner("PROJECT_BROADCAST", True) is True