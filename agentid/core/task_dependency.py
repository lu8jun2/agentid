"""Task dependency checker — validates DAG structure and determines which nodes are ready."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentid.models.task_tree import TaskNode


# ── DAG Validation ────────────────────────────────────────────────────────────

class CycleError(Exception):
    """Raised when the node graph contains a cycle."""
    pass


def validate_dag(nodes: list[TaskNode]) -> None:
    """
    Validate that the node graph is a proper DAG (no cycles, all parent_ids exist).

    Raises:
        CycleError: if a cycle is detected.
        ValueError: if a parent_id references a non-existent node.
    """
    node_map = {n.id: n for n in nodes}
    if len(node_map) != len(nodes):
        raise ValueError("Duplicate node IDs found")

    # Kahn's algorithm for cycle detection
    in_degree = {nid: 0 for nid in node_map}
    for n in nodes:
        for pid in (n.parent_ids or []):
            if pid not in node_map:
                raise ValueError(f"Node {n.id} references non-existent parent {pid}")
            in_degree[n.id] += 1

    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    visited = 0
    while queue:
        nid = queue.pop(0)
        visited += 1
        for child_id in (node_map[nid].child_ids or []):
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)

    if visited != len(nodes):
        raise CycleError(f"Cycle detected in task graph — {len(nodes) - visited} nodes unreachable")


# ── Dependency Checking ──────────────────────────────────────────────────────

def dependencies_met(node: TaskNode, completed_ids: set[str]) -> bool:
    """
    Return True when all of a node's parent nodes have been completed.

    A node with empty parent_ids (root) is always ready.
    """
    if not node.parent_ids:
        return True
    return all(pid in completed_ids for pid in node.parent_ids)


def ready_nodes(nodes: list[TaskNode]) -> list[TaskNode]:
    """
    Return all nodes whose dependencies are satisfied and are still pending.
    """
    completed = {n.id for n in nodes if n.status == "completed"}
    return [
        n for n in nodes
        if n.status == "pending"
        and dependencies_met(n, completed)
    ]


def compute_depth(nodes: list[TaskNode]) -> dict[str, int]:
    """
    Compute the DAG depth (longest path from any root) for each node.
    Returns a dict mapping node_id -> depth (root = 0).
    """
    node_map = {n.id: n for n in nodes}
    depth: dict[str, int] = {}

    def dfs_depth(nid: str) -> int:
        if nid in depth:
            return depth[nid]
        node = node_map[nid]
        if not node.parent_ids:
            depth[nid] = 0
        else:
            depth[nid] = max(dfs_depth(pid) for pid in node.parent_ids) + 1
        return depth[nid]

    for nid in node_map:
        dfs_depth(nid)
    return depth


def topological_order(nodes: list[TaskNode]) -> list[TaskNode]:
    """
    Return nodes in topological order (all parents before children).
    Raises CycleError if the graph has a cycle.
    """
    validate_dag(nodes)
    node_map = {n.id: n for n in nodes}
    in_degree = {nid: len(n.parent_ids or []) for nid, n in node_map.items()}
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    ordered = []
    while queue:
        nid = queue.pop(0)
        ordered.append(node_map[nid])
        for child_id in (node_map[nid].child_ids or []):
            in_degree[child_id] -= 1
            if in_degree[child_id] == 0:
                queue.append(child_id)
    return ordered


# ── Node execution state machine ──────────────────────────────────────────────

def can_start(node: TaskNode, completed_ids: set[str]) -> tuple[bool, str]:
    """
    Check if a node can transition to in_progress.
    Returns (allowed, reason).
    """
    if node.status not in ("pending", "assigned"):
        return False, f"Node status is '{node.status}', must be 'pending' or 'assigned'"
    if not dependencies_met(node, completed_ids):
        pending = [pid for pid in (node.parent_ids or []) if pid not in completed_ids]
        return False, f"Waiting on parent nodes: {pending}"
    return True, ""


def can_complete(node: TaskNode) -> tuple[bool, str]:
    """
    Check if a node can transition to review/completed.
    """
    if node.status not in ("in_progress",):
        return False, f"Node status is '{node.status}', must be 'in_progress'"
    if not node.result_summary and not node.delivery_url:
        return False, "Node must have result_summary or delivery_url before completing"
    return True, ""
