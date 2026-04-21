"""
IMDB/Douban-style reputation scoring engine.
Final score: 0.0 - 10.0, displayed to one decimal place.
Anti-gaming: Bayesian smoothing, log scaling, global mean anchoring.

Peer ratings are cast by other AI agents (not humans), making the system
fully agent-native. Future: incentive mechanism for agents to rate peers.
"""
import math
from dataclasses import dataclass, field
from agentid.config import settings


@dataclass
class ScoreInput:
    project_count: int = 0
    active_projects: int = 0
    total_tokens: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    collaboration_count: int = 0
    account_age_days: int = 0
    peer_ratings: list[float] = field(default_factory=list)
    # domain_events: {"coding": {"tasks": 5, "tokens": 12000, "peer_ratings": [8.0, 7.5]}}
    domain_events: dict[str, dict] = field(default_factory=dict)


def _project_count_score(count: int) -> float:
    return min(10.0, math.log1p(count) / math.log1p(100) * 10)


def _survival_rate_score(active: int, total: int) -> float:
    if total == 0:
        return 0.0
    # Bayesian smoothing: assume 3 ghost projects to penalize new agents
    return (active + 1) / (total + 3) * 10


def _token_efficiency_score(tasks: int, tokens: int) -> float:
    if tokens == 0:
        return 0.0
    tasks_per_1k = (tasks / tokens) * 1000
    return min(10.0, math.log1p(tasks_per_1k) / math.log1p(10) * 10)


def _collaboration_score(count: int) -> float:
    return min(10.0, math.log1p(count) / math.log1p(50) * 10)


def _longevity_score(age_days: int) -> float:
    return min(10.0, age_days / 365 * 10)


def _bayesian_peer_score(ratings: list[float]) -> float:
    """IMDB Bayesian average: WR = (v/(v+m))*R + (m/(v+m))*C"""
    C = settings.global_score_mean
    m = settings.peer_rating_min_votes
    v = len(ratings)
    if v == 0:
        return C
    R = sum(ratings) / v
    return (v / (v + m)) * R + (m / (v + m)) * C


WEIGHTS = {
    "project_count": 0.15,
    "survival_rate": 0.20,
    "token_efficiency": 0.15,
    "collaboration": 0.10,
    "longevity": 0.10,
    "peer_rating": 0.30,
}


def compute_score(inp: ScoreInput) -> dict:
    components = {
        "project_count_score": _project_count_score(inp.project_count),
        "survival_rate_score": _survival_rate_score(inp.active_projects, inp.project_count),
        "token_efficiency_score": _token_efficiency_score(inp.tasks_completed, inp.total_tokens),
        "collaboration_score": _collaboration_score(inp.collaboration_count),
        "longevity_score": _longevity_score(inp.account_age_days),
        "peer_rating_score": _bayesian_peer_score(inp.peer_ratings),
    }

    final = (
        components["project_count_score"]    * WEIGHTS["project_count"]   +
        components["survival_rate_score"]    * WEIGHTS["survival_rate"]   +
        components["token_efficiency_score"] * WEIGHTS["token_efficiency"] +
        components["collaboration_score"]    * WEIGHTS["collaboration"]   +
        components["longevity_score"]        * WEIGHTS["longevity"]       +
        components["peer_rating_score"]      * WEIGHTS["peer_rating"]
    )

    # Domain scores — same algorithm applied per domain subset
    domain_scores = {}
    for domain, data in inp.domain_events.items():
        d_inp = ScoreInput(
            tasks_completed=data.get("tasks", 0),
            total_tokens=data.get("tokens", 0),
            peer_ratings=data.get("peer_ratings", []),
        )
        domain_scores[domain] = round(
            _token_efficiency_score(d_inp.tasks_completed, d_inp.total_tokens) * 0.5 +
            _bayesian_peer_score(d_inp.peer_ratings) * 0.5,
            2,
        )

    return {
        "score": round(final, 1),
        "components": {k: round(v, 2) for k, v in components.items()},
        "domain_scores": domain_scores,
    }
