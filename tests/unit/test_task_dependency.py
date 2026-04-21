"""Unit tests for task dependency checker and DAG validation."""
import pytest
from dataclasses import dataclass, field
from agentid.core.task_dependency import (
    validate_dag,
    CycleError,
    dependencies_met,
    ready_nodes,
    compute_depth,
    topological_order,
    can_start,
    can_complete,
)


@dataclass
class FakeNode:
    id: str
    status: str = "pending"
    parent_ids: list = field(default_factory=list)
    child_ids: list = field(default_factory=list)
    result_summary: str | None = None
    delivery_url: str | None = None


class TestValidateDag:
    def test_valid_linear_chain(self):
        nodes = [
            FakeNode(id="a", parent_ids=[], child_ids=["b"]),
            FakeNode(id="b", parent_ids=["a"], child_ids=["c"]),
            FakeNode(id="c", parent_ids=["b"], child_ids=[]),
        ]
        validate_dag(nodes)  # no exception

    def test_valid_parallel(self):
        # a -> [b, c] -> d
        nodes = [
            FakeNode(id="a", parent_ids=[], child_ids=["b", "c"]),
            FakeNode(id="b", parent_ids=["a"], child_ids=["d"]),
            FakeNode(id="c", parent_ids=["a"], child_ids=["d"]),
            FakeNode(id="d", parent_ids=["b", "c"], child_ids=[]),
        ]
        validate_dag(nodes)

    def test_single_node_is_valid(self):
        nodes = [FakeNode(id="solo", parent_ids=[], child_ids=[])]
        validate_dag(nodes)

    def test_cycle_self_loop(self):
        # a depends on itself — simple cycle
        nodes = [
            FakeNode(id="a", parent_ids=["a"], child_ids=[]),
        ]
        with pytest.raises(CycleError):
            validate_dag(nodes)

    def test_cycle_chain(self):
        # a -> b -> c, where c has itself as parent (self-loop on c)
        nodes = [
            FakeNode(id="a", parent_ids=[], child_ids=["b"]),
            FakeNode(id="b", parent_ids=["a"], child_ids=["c"]),
            FakeNode(id="c", parent_ids=["b", "c"], child_ids=[]),  # c depends on itself
        ]
        with pytest.raises(CycleError):
            validate_dag(nodes)

    def test_missing_parent_ref(self):
        nodes = [
            FakeNode(id="a", parent_ids=[], child_ids=["b"]),
            FakeNode(id="b", parent_ids=["nonexistent"], child_ids=[]),
        ]
        with pytest.raises(ValueError, match="non-existent parent"):
            validate_dag(nodes)

    def test_duplicate_ids(self):
        nodes = [
            FakeNode(id="dup", parent_ids=[], child_ids=["dup"]),
            FakeNode(id="dup", parent_ids=[], child_ids=[]),
        ]
        with pytest.raises(ValueError, match="Duplicate"):
            validate_dag(nodes)


class TestDependenciesMet:
    def test_root_always_ready(self):
        node = FakeNode(id="root", parent_ids=[])
        assert dependencies_met(node, set())

    def test_all_parents_done(self):
        node = FakeNode(id="c", parent_ids=["a", "b"])
        assert dependencies_met(node, {"a", "b"})

    def test_some_parents_pending(self):
        node = FakeNode(id="c", parent_ids=["a", "b"])
        assert not dependencies_met(node, {"a"})

    def test_empty_parent_ids_root(self):
        node = FakeNode(id="root")
        assert dependencies_met(node, set())


class TestReadyNodes:
    def test_single_ready_node(self):
        nodes = [FakeNode(id="a")]
        assert ready_nodes(nodes) == [nodes[0]]

    def test_waits_for_parent(self):
        nodes = [
            FakeNode(id="a"),
            FakeNode(id="b", parent_ids=["a"]),
        ]
        assert ready_nodes(nodes) == [nodes[0]]  # b not ready

    def test_completed_parent_unblocks_child(self):
        nodes = [
            FakeNode(id="a", status="completed"),
            FakeNode(id="b", parent_ids=["a"], status="pending"),
        ]
        ready = ready_nodes(nodes)
        assert nodes[1] in ready


class TestComputeDepth:
    def test_single_root_depth_0(self):
        nodes = [FakeNode(id="a")]
        d = compute_depth(nodes)
        assert d["a"] == 0

    def test_linear_depth(self):
        nodes = [
            FakeNode(id="a", parent_ids=[], child_ids=["b"]),
            FakeNode(id="b", parent_ids=["a"], child_ids=["c"]),
            FakeNode(id="c", parent_ids=["b"], child_ids=[]),
        ]
        d = compute_depth(nodes)
        assert d["a"] == 0
        assert d["b"] == 1
        assert d["c"] == 2

    def test_parallel_merge_depth(self):
        # a -> b -> d
        # a -> c -> d
        # d should be depth 2
        nodes = [
            FakeNode(id="a", parent_ids=[], child_ids=["b", "c"]),
            FakeNode(id="b", parent_ids=["a"], child_ids=["d"]),
            FakeNode(id="c", parent_ids=["a"], child_ids=["d"]),
            FakeNode(id="d", parent_ids=["b", "c"], child_ids=[]),
        ]
        d = compute_depth(nodes)
        assert d["a"] == 0
        assert d["b"] == 1
        assert d["c"] == 1
        assert d["d"] == 2


class TestTopologicalOrder:
    def test_reversed_order(self):
        nodes = [
            FakeNode(id="a", parent_ids=[], child_ids=["b"]),
            FakeNode(id="b", parent_ids=["a"], child_ids=[]),
        ]
        order = topological_order(nodes)
        assert order[0].id == "a"
        assert order[1].id == "b"


class TestCanStart:
    def test_pending_with_met_deps(self):
        node = FakeNode(id="a", status="pending", parent_ids=[])
        ok, reason = can_start(node, set())
        assert ok

    def test_in_progress_blocked(self):
        node = FakeNode(id="a", status="in_progress", parent_ids=[])
        ok, reason = can_start(node, set())
        assert not ok

    def test_unmet_dependencies(self):
        node = FakeNode(id="c", status="pending", parent_ids=["a", "b"])
        ok, reason = can_start(node, {"a"})
        assert not ok
        assert "Waiting on parent" in reason


class TestCanComplete:
    def test_in_progress_with_result(self):
        node = FakeNode(id="a", status="in_progress", result_summary="Done!")
        ok, _ = can_complete(node)
        assert ok

    def test_in_progress_with_url(self):
        node = FakeNode(id="a", status="in_progress", delivery_url="https://example.com")
        ok, _ = can_complete(node)
        assert ok

    def test_pending_blocked(self):
        node = FakeNode(id="a", status="pending")
        ok, _ = can_complete(node)
        assert not ok

    def test_no_result_blocked(self):
        node = FakeNode(id="a", status="in_progress")
        ok, reason = can_complete(node)
        assert not ok
        assert "result_summary or delivery_url" in reason
