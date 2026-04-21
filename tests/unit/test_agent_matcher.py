"""Unit tests for agent matching logic."""
import pytest
from agentid.core.agent_matcher import domain_affinity, DOMAIN_TO_SCORE_KEY


class TestDomainAffinity:
    def test_exact_match(self):
        scores = {"coding": 8.5, "writing": 7.0, "overall": 7.5}
        assert domain_affinity("coding", scores) == 8.5

    def test_falls_back_to_overall(self):
        scores = {"writing": 7.0, "overall": 7.5}
        assert domain_affinity("coding", scores) == 7.5

    def test_falls_back_to_max(self):
        scores = {"writing": 9.0, "research": 6.0}
        assert domain_affinity("coding", scores) == 9.0

    def test_empty_scores(self):
        assert domain_affinity("coding", {}) == 0.0

    def test_none_scores(self):
        assert domain_affinity("coding", None) == 0.0


class TestDomainMap:
    def test_all_domains_defined(self):
        expected = {"coding", "writing", "research", "data", "creative", "devops", "general"}
        assert set(DOMAIN_TO_SCORE_KEY.keys()) == expected

    def test_general_maps_to_overall(self):
        assert DOMAIN_TO_SCORE_KEY["general"] == "overall"
