from agentid.worker.scheduler import _task_event_weight, PRACTICE_TASK_WEIGHT
from agentid.config import settings


def test_paid_task_weight_is_full():
    assert _task_event_weight({"task_kind": "paid"}) == 1.0
    assert _task_event_weight({}) == 1.0


def test_practice_task_weight_is_reduced():
    assert _task_event_weight({"task_kind": "practice"}) == PRACTICE_TASK_WEIGHT


def test_practice_peer_rating_should_shrink_toward_global_mean():
    raw_score = 10.0
    weighted_score = settings.global_score_mean + (raw_score - settings.global_score_mean) * PRACTICE_TASK_WEIGHT
    assert settings.global_score_mean < weighted_score < raw_score
