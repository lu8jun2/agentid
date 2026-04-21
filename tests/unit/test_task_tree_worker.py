"""Unit tests for task_tree_worker — auto-assignment logic without DB."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from agentid.worker.task_tree_worker import _check_tree_completion


class FakeNode:
    def __init__(self, id, status, tree_id="tree-1"):
        self.id = id
        self.status = status
        self.tree_id = tree_id


class FakeTree:
    def __init__(self, id, status="executing"):
        self.id = id
        self.status = status
        self.updated_at = None


class TestCheckTreeCompletion:
    async def _run_check(self, tree, nodes):
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = nodes
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)
        await _check_tree_completion(mock_db, tree)

    async def test_all_completed_sets_completed(self):
        tree = FakeTree("t1")
        nodes = [FakeNode("n1", "completed"), FakeNode("n2", "completed")]
        await self._run_check(tree, nodes)
        assert tree.status == "completed"

    async def test_some_failed_sets_partial(self):
        tree = FakeTree("t1")
        nodes = [FakeNode("n1", "completed"), FakeNode("n2", "failed")]
        await self._run_check(tree, nodes)
        assert tree.status == "partial"

    async def test_all_failed_sets_partial(self):
        tree = FakeTree("t1")
        nodes = [FakeNode("n1", "failed"), FakeNode("n2", "failed")]
        await self._run_check(tree, nodes)
        assert tree.status == "partial"

    async def test_mixed_active_keeps_executing(self):
        tree = FakeTree("t1")
        nodes = [FakeNode("n1", "completed"), FakeNode("n2", "in_progress")]
        await self._run_check(tree, nodes)
        assert tree.status == "executing"

    async def test_empty_nodes_keeps_executing(self):
        tree = FakeTree("t1")
        await self._run_check(tree, [])
        assert tree.status == "executing"

    async def test_all_pending_keeps_executing(self):
        tree = FakeTree("t1")
        nodes = [FakeNode("n1", "pending"), FakeNode("n2", "pending")]
        await self._run_check(tree, nodes)
        assert tree.status == "executing"

    async def test_all_skipped_is_partial(self):
        tree = FakeTree("t1")
        nodes = [FakeNode("n1", "skipped"), FakeNode("n2", "skipped")]
        await self._run_check(tree, nodes)
        assert tree.status == "partial"

    async def test_completed_plus_skipped_is_partial(self):
        tree = FakeTree("t1")
        nodes = [FakeNode("n1", "completed"), FakeNode("n2", "skipped")]
        await self._run_check(tree, nodes)
        assert tree.status == "partial"
