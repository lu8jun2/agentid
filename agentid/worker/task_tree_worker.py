"""Task Tree auto-assignment worker — assigns ready nodes to the best available agent."""
import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_
from agentid.db.session import AsyncSessionLocal
from agentid.models.task_tree import TaskTree, TaskNode
from agentid.core.task_dependency import dependencies_met
from agentid.core.agent_matcher import select_best_agent

log = logging.getLogger("worker.task_tree")

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def process_ready_nodes(interval_minutes: int = 5):
    """
    Find all trees in 'executing' state, check each pending node's dependencies,
    and auto-assign ready nodes to the best available agent.
    """
    log.info("TaskTree worker: scanning for ready nodes...")

    async with AsyncSessionLocal() as db:
        # Get all executing trees
        trees_result = await db.execute(
            select(TaskTree).where(TaskTree.status == "executing")
        )
        trees = trees_result.scalars().all()

        assigned_count = 0
        skipped_count = 0

        for tree in trees:
            assigned, skipped = await _process_tree(db, tree)
            assigned_count += assigned
            skipped_count += skipped

        await db.commit()

    log.info(
        f"TaskTree worker done — assigned: {assigned_count}, "
        f"no-agent-skipped: {skipped_count}"
    )


async def _process_tree(db, tree: TaskTree) -> tuple[int, int]:
    """Process all pending nodes in a single tree. Returns (assigned, skipped)."""
    nodes_result = await db.execute(
        select(TaskNode).where(TaskNode.tree_id == tree.id)
    )
    nodes = nodes_result.scalars().all()

    completed_ids = {n.id for n in nodes if n.status == "completed"}
    pending_ids = {n.id for n in nodes if n.status == "pending"}
    assigned_ids = {n.id for n in nodes if n.status == "assigned"}
    already_handled = pending_ids | assigned_ids

    assigned = 0
    skipped = 0

    for node in nodes:
        if node.status != "pending":
            continue
        if node.id not in pending_ids:
            continue

        if not dependencies_met(node, completed_ids):
            continue

        # Find best agent for this domain
        matches = await select_best_agent(db, node.domain, min_score=5.0, limit=1)
        if not matches:
            log.warning(
                f"No eligible agent found for node {node.id[:8]} "
                f"(domain={node.domain}), skipping"
            )
            skipped += 1
            continue

        best = matches[0]
        node.assigned_agent_did = best.did
        node.status = "assigned"
        node.guidance = (
            node.guidance
            or f"Auto-assigned by AgentID TaskTree worker. Domain: {node.domain}."
        )
        log.info(
            f"Node {node.id[:8]} assigned to {best.did} "
            f"(domain={node.domain}, score={best.domain_score})"
        )
        assigned += 1

    # Check if tree is complete
    await _check_tree_completion(db, tree)

    return assigned, skipped


async def _check_tree_completion(db, tree: TaskTree):
    """Update tree status when all nodes are terminal."""
    nodes_result = await db.execute(
        select(TaskNode).where(TaskNode.tree_id == tree.id)
    )
    nodes = nodes_result.scalars().all()

    statuses = [n.status for n in nodes]
    total = len(statuses)
    if total == 0:
        return

    completed = statuses.count("completed")
    failed = statuses.count("failed")
    skipped = statuses.count("skipped")
    active = statuses.count("pending") + statuses.count("assigned") + statuses.count("in_progress") + statuses.count("review")

    if completed + failed + skipped == total:
        if failed == 0 and skipped == 0:
            tree.status = "completed"
        else:
            tree.status = "partial"
        tree.updated_at = datetime.now(timezone.utc)
        log.info(f"Tree {tree.id[:8]} marked {tree.status} ({completed} ok, {failed} failed, {skipped} skipped)")


def start_scheduler(interval_minutes: int = 5):
    """Start the background scheduler for node auto-assignment."""
    sched = get_scheduler()
    if not sched.running:
        sched.add_job(
            process_ready_nodes,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="task_tree_auto_assign",
            replace_existing=True,
        )
        sched.start()
        log.info(f"TaskTree scheduler started — auto-assign every {interval_minutes}min")


def stop_scheduler():
    """Stop the scheduler gracefully."""
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
        log.info("TaskTree scheduler stopped")


async def run_once():
    """Run one processing pass immediately (CLI entry point)."""
    await process_ready_nodes()
