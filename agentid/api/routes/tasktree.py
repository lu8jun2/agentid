"""TaskTree and TaskNode API routes — DAG-based task decomposition."""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from pydantic import BaseModel, Field

from agentid.db.session import get_db
from agentid.api.deps import get_api_key
from agentid.models.agent import Agent
from agentid.models.authorization import APIKey
from agentid.models.task_tree import TaskTree, TaskNode
from agentid.models.score import ReputationScore
from agentid.core.decomposer import decompose_task, DecompositionResult
from agentid.core.task_dependency import validate_dag, CycleError


router = APIRouter()

# ── Request/Response Models ───────────────────────────────────────────────────

class CreateTaskTreeRequest(BaseModel):
    client_id: int
    title: str = Field(..., max_length=512)
    description: str | None = None
    total_reward: float = Field(default=0.0, ge=0)
    domain_hint: str = Field(default="general", max_length=64)
    llm_decomposition: bool = True  # if False, create single-node tree


class CreateNodeRequest(BaseModel):
    title: str = Field(..., max_length=512)
    description: str | None = None
    domain: str = Field(default="general", max_length=64)
    parent_ids: list[str] = Field(default_factory=list)
    estimated_tokens: int = Field(default=0, ge=0)
    estimated_minutes: int = Field(default=0, ge=0)
    reward_fraction: float = Field(default=0.0, ge=0, le=1.0)
    guidance: str | None = None


class AssignNodeRequest(BaseModel):
    agent_did: str


class UpdateNodeRequest(BaseModel):
    status: str | None = None
    result_summary: str | None = None
    delivery_url: str | None = None


class ReviewNodeRequest(BaseModel):
    approve: bool
    feedback: str | None = None


class RetryNodeRequest(BaseModel):
    reason: str | None = None


class NodeResponse(BaseModel):
    id: str
    tree_id: str
    title: str
    description: str | None
    domain: str
    parent_ids: list[str]
    child_ids: list[str]
    status: str
    assigned_agent_did: str | None
    reward_fraction: float
    estimated_tokens: int
    estimated_minutes: int
    started_at: datetime | None
    completed_at: datetime | None
    result_summary: str | None
    delivery_url: str | None
    failure_reason: str | None
    guidance: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class TaskTreeResponse(BaseModel):
    id: str
    client_id: int
    title: str
    description: str | None
    root_node_id: str
    status: str
    total_reward: float
    depth: int
    node_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskTreeDetailResponse(BaseModel):
    tree: TaskTreeResponse
    nodes: list[NodeResponse]


class ProgressResponse(BaseModel):
    tree_id: str
    total: int
    pending: int
    assigned: int
    in_progress: int
    review: int
    completed: int
    failed: int
    skipped: int
    pct: float


# ── Internal helpers ───────────────────────────────────────────────────────────

VALID_NODE_STATUSES = {"pending", "assigned", "in_progress", "review", "completed", "failed", "skipped"}
VALID_TREE_STATUSES = {"planning", "executing", "completed", "partial", "cancelled"}


def _compute_tree_metrics(tree_id: str, nodes: list[TaskNode]):
    counts = {s: 0 for s in VALID_NODE_STATUSES}
    for n in nodes:
        if n.status in counts:
            counts[n.status] += 1
    total = len(nodes)
    completed = counts["completed"]
    pct = round(completed / total * 100, 1) if total > 0 else 0.0
    return counts, total, completed, pct


def _build_child_ids(nodes: list[TaskNode]):
    child_map: dict[str, list[str]] = {}
    for n in nodes:
        for pid in (n.parent_ids or []):
            child_map.setdefault(pid, []).append(n.id)
    return child_map


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=TaskTreeDetailResponse, status_code=201)
async def create_task_tree(
    body: CreateTaskTreeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new task tree. If llm_decomposition=True, calls Claude to decompose into a DAG."""
    tree_id = str(uuid.uuid4())

    if body.llm_decomposition:
        # ── LLM decomposition path ──────────────────────────────────────────────
        try:
            result = decompose_task(
                description=body.description or body.title,
                domain_hint=body.domain_hint,
                reward=body.total_reward,
            )
        except Exception as exc:
            raise HTTPException(502, f"LLM decomposition failed: {exc}") from exc

        # Assign UUIDs to LLM-returned nodes, building node_map (title → node)
        llm_nodes = result["nodes"]
        node_map: dict[str, TaskNode] = {}   # id -> TaskNode
        id_map: dict[str, str] = {}           # temp_id (or "root") -> real_id

        # Root nodes from LLM (those with empty/null parent_ids) get special treatment
        root_ids_from_llm = {n["title"]: str(uuid.uuid4()) for n in llm_nodes if not n["parent_ids"]}
        child_ids_map: dict[str, list[str]] = {}

        nodes: list[TaskNode] = []

        for n in llm_nodes:
            real_id = str(uuid.uuid4())
            parent_ids = []
            for pid in (n["parent_ids"] or []):
                if pid in id_map:
                    parent_ids.append(id_map[pid])
                else:
                    # Fallback: pid references a title, find by title
                    for ln in llm_nodes:
                        if ln["title"] == pid:
                            parent_ids.append(id_map.get(ln["title"], str(uuid.uuid4())))
                            break

            # Resolve parent titles to real IDs via id_map
            resolved_parent_ids = []
            for p in n.get("parent_ids") or []:
                if p in id_map:
                    resolved_parent_ids.append(id_map[p])
                else:
                    for ln in llm_nodes:
                        if ln["title"] == p and ln["title"] in id_map:
                            resolved_parent_ids.append(id_map[ln["title"]])
                            break

            node = TaskNode(
                id=real_id,
                tree_id=tree_id,
                title=n["title"],
                description=n.get("description"),
                domain=n.get("domain", body.domain_hint),
                parent_ids=resolved_parent_ids,
                child_ids=[],
                status="pending",
                reward_fraction=n.get("reward_fraction", 0.0),
                estimated_tokens=n.get("estimated_tokens", 0),
                estimated_minutes=n.get("estimated_minutes", 0),
                guidance=n.get("guidance"),
                created_at=datetime.utcnow(),
            )
            id_map[n["title"]] = real_id
            node_map[real_id] = node
            nodes.append(node)
            db.add(node)

        # Second pass: fill in child_ids from parent_ids
        for n in nodes:
            for pid in (n.parent_ids or []):
                child_ids_map.setdefault(pid, []).append(n.id)
        for n in nodes:
            n.child_ids = child_ids_map.get(n.id, [])

        # Determine root_node_id: first root (empty parent_ids)
        root_node = next((n for n in nodes if not n.parent_ids), None)
        root_node_id = root_node.id if root_node else nodes[0].id if nodes else tree_id

        # Validate DAG
        try:
            validate_dag(nodes)
        except (CycleError, ValueError) as exc:
            raise HTTPException(422, f"Invalid DAG returned by LLM: {exc}") from exc

        depth = max(
            (len(n.parent_ids) for n in nodes), default=0
        )
        node_count = len(nodes)

    else:
        # ── Single-node path (no LLM) ────────────────────────────────────────────
        root_id = str(uuid.uuid4())
        root = TaskNode(
            id=root_id,
            tree_id=tree_id,
            title=body.title,
            description=body.description,
            domain=body.domain_hint,
            parent_ids=[],
            child_ids=[],
            status="pending",
            reward_fraction=1.0,
            guidance=None,
            created_at=datetime.utcnow(),
        )
        db.add(root)
        nodes = [root]
        root_node_id = root_id
        depth = 0
        node_count = 1

    tree = TaskTree(
        id=tree_id,
        client_id=body.client_id,
        title=body.title,
        description=body.description,
        root_node_id=root_node_id,
        status="executing",
        total_reward=body.total_reward,
        depth=depth,
        node_count=node_count,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(tree)
    await db.commit()

    return TaskTreeDetailResponse(
        tree=TaskTreeResponse.model_validate(tree),
        nodes=[NodeResponse.model_validate(n) for n in nodes],
    )


@router.get("/my", response_model=list[TaskTreeResponse])
async def list_my_trees(
    client_id: int = Query(...),
    status: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List task trees for a client."""
    query = select(TaskTree).where(TaskTree.client_id == client_id)
    if status:
        query = query.where(TaskTree.status == status)
    query = query.order_by(TaskTree.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    trees = result.scalars().all()
    return [TaskTreeResponse.model_validate(t) for t in trees]


@router.get("/{tree_id}", response_model=TaskTreeDetailResponse)
async def get_task_tree(tree_id: str, db: AsyncSession = Depends(get_db)):
    """Get full task tree with all nodes."""
    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == tree_id))
    tree = tree_result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "TaskTree not found")

    nodes_result = await db.execute(
        select(TaskNode).where(TaskNode.tree_id == tree_id).order_by(TaskNode.created_at)
    )
    nodes = nodes_result.scalars().all()
    return TaskTreeDetailResponse(
        tree=TaskTreeResponse.model_validate(tree),
        nodes=[NodeResponse.model_validate(n) for n in nodes],
    )


@router.post("/node", response_model=NodeResponse, status_code=201)
async def add_node(
    body: CreateNodeRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Add a child node to an existing tree."""
    # Find parent nodes
    parent_nodes = []
    for pid in body.parent_ids:
        result = await db.execute(select(TaskNode).where(TaskNode.id == pid))
        pn = result.scalar_one_or_none()
        if not pn:
            raise HTTPException(404, f"Parent node {pid} not found")
        parent_nodes.append(pn)

    if not parent_nodes:
        raise HTTPException(422, "At least one parent_id is required")

    tree_id = parent_nodes[0].tree_id

    # Verify all parents belong to same tree
    for pn in parent_nodes[1:]:
        if pn.tree_id != tree_id:
            raise HTTPException(422, "All parent nodes must belong to the same tree")

    node_id = str(uuid.uuid4())
    node = TaskNode(
        id=node_id,
        tree_id=tree_id,
        title=body.title,
        description=body.description,
        domain=body.domain,
        parent_ids=body.parent_ids,
        child_ids=[],
        status="pending",
        reward_fraction=body.reward_fraction,
        estimated_tokens=body.estimated_tokens,
        estimated_minutes=body.estimated_minutes,
        guidance=body.guidance,
        created_at=datetime.utcnow(),
    )
    db.add(node)

    # Update parents' child_ids
    for pn in parent_nodes:
        if node_id not in pn.child_ids:
            pn.child_ids = pn.child_ids + [node_id]

    # Update tree node_count
    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == tree_id))
    tree = tree_result.scalar_one_or_none()
    if tree:
        tree.node_count += 1
        tree.updated_at = datetime.utcnow()

    await db.commit()
    return NodeResponse.model_validate(node)


@router.get("/node/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaskNode).where(TaskNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")
    return NodeResponse.model_validate(node)


@router.post("/node/{node_id}/assign", response_model=NodeResponse)
async def assign_node(
    node_id: str,
    body: AssignNodeRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Manually assign a node to an agent (overrides automatic matching)."""
    result = await db.execute(select(TaskNode).where(TaskNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")

    # Verify agent exists
    agent_result = await db.execute(select(Agent).where(Agent.did == body.agent_did))
    if not agent_result.scalar_one_or_none():
        raise HTTPException(404, f"Agent {body.agent_did} not found")

    node.assigned_agent_did = body.agent_did
    node.status = "assigned"
    node.guidance = node.guidance or f"Assigned to {body.agent_did}"

    # Update tree status
    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == node.tree_id))
    tree = tree_result.scalar_one_or_none()
    if tree and tree.status == "planning":
        tree.status = "executing"
        tree.updated_at = datetime.utcnow()

    await db.commit()
    return NodeResponse.model_validate(node)


@router.post("/node/{node_id}/update", response_model=NodeResponse)
async def update_node(
    node_id: str,
    body: UpdateNodeRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Agent updates node status / result (called by executing agent)."""
    result = await db.execute(select(TaskNode).where(TaskNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")

    if body.status:
        if body.status not in VALID_NODE_STATUSES:
            raise HTTPException(422, f"Invalid status: {body.status}")
        node.status = body.status
        if body.status == "in_progress" and not node.started_at:
            node.started_at = datetime.utcnow()
        if body.status in ("completed", "failed", "skipped"):
            node.completed_at = datetime.utcnow()

    if body.result_summary is not None:
        node.result_summary = body.result_summary
    if body.delivery_url is not None:
        node.delivery_url = body.delivery_url

    # Update tree updated_at
    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == node.tree_id))
    tree = tree_result.scalar_one_or_none()
    if tree:
        tree.updated_at = datetime.utcnow()

    await db.commit()
    return NodeResponse.model_validate(node)


@router.post("/node/{node_id}/review", response_model=NodeResponse)
async def review_node(
    node_id: str,
    body: ReviewNodeRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Client approves or rejects a node (moves from 'review' to 'completed' or 'failed')."""
    result = await db.execute(select(TaskNode).where(TaskNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")

    if node.status != "review":
        raise HTTPException(422, f"Node must be in 'review' status, got '{node.status}'")

    if body.feedback:
        node.failure_reason = body.feedback

    if body.approve:
        node.status = "completed"
        node.completed_at = datetime.utcnow()
    else:
        node.status = "failed"
        node.completed_at = datetime.utcnow()

    # Update tree
    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == node.tree_id))
    tree = tree_result.scalar_one_or_none()
    if tree:
        tree.updated_at = datetime.utcnow()

    await db.commit()
    return NodeResponse.model_validate(node)


@router.post("/node/{node_id}/retry", response_model=NodeResponse)
async def retry_node(
    node_id: str,
    body: RetryNodeRequest,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Reset a failed node for retry."""
    result = await db.execute(select(TaskNode).where(TaskNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")

    if node.status not in ("failed", "skipped"):
        raise HTTPException(422, f"Can only retry failed/skipped nodes, got '{node.status}'")

    node.status = "pending"
    node.started_at = None
    node.completed_at = None
    node.failure_reason = body.reason
    node.assigned_agent_did = None

    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == node.tree_id))
    tree = tree_result.scalar_one_or_none()
    if tree:
        tree.status = "executing"
        tree.updated_at = datetime.utcnow()

    await db.commit()
    return NodeResponse.model_validate(node)


@router.get("/{tree_id}/progress", response_model=ProgressResponse)
async def get_progress(tree_id: str, db: AsyncSession = Depends(get_db)):
    """Get execution progress for a task tree."""
    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == tree_id))
    tree = tree_result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "TaskTree not found")

    nodes_result = await db.execute(select(TaskNode).where(TaskNode.tree_id == tree_id))
    nodes = nodes_result.scalars().all()

    counts, total, completed, pct = _compute_tree_metrics(tree_id, nodes)

    # Auto-update tree status based on node states
    if completed == total and total > 0:
        tree.status = "completed"
        tree.updated_at = datetime.utcnow()
        await db.commit()

    return ProgressResponse(
        tree_id=tree_id,
        total=total,
        pending=counts.get("pending", 0),
        assigned=counts.get("assigned", 0),
        in_progress=counts.get("in_progress", 0),
        review=counts.get("review", 0),
        completed=completed,
        failed=counts.get("failed", 0),
        skipped=counts.get("skipped", 0),
        pct=pct,
    )


@router.get("/node/{node_id}/eligible-agents", response_model=list[dict])
async def get_eligible_agents(
    node_id: str,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """Return top agents for a node's domain (by domain score), for assignment."""
    result = await db.execute(select(TaskNode).where(TaskNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(404, "Node not found")

    domain = node.domain

    # Get top agents by domain score
    subq = (
        select(
            ReputationScore.agent_id,
            ReputationScore.domain_scores,
            ReputationScore.score,
        )
        .where(ReputationScore.score >= 5.0)
        .order_by(ReputationScore.score.desc())
        .limit(50)
    )
    agents_result = await db.execute(
        select(Agent, ReputationScore)
        .join(ReputationScore, Agent.id == ReputationScore.agent_id)
        .where(Agent.is_active == True, ReputationScore.score >= 5.0)
        .order_by(ReputationScore.score.desc())
        .limit(limit)
    )
    rows = agents_result.fetchall()

    eligible = []
    for agent, score in rows:
        domain_score = score.domain_scores.get(domain, score.score) if score.domain_scores else score.score
        eligible.append({
            "did": agent.did,
            "name": agent.name,
            "total_score": round(score.score, 2),
            "domain_score": round(domain_score, 2),
            "domain": domain,
        })

    return eligible


# ── Auto-assignment & Settlement ───────────────────────────────────────────────

class SettleResponse(BaseModel):
    tree_id: str
    total_reward: float
    settlements: list[dict]
    settled_count: int
    skipped_count: int


@router.post("/{tree_id}/auto-assign", response_model=dict)
async def trigger_auto_assign(
    tree_id: str,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger auto-assignment for a specific tree (bypasses scheduler wait)."""
    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == tree_id))
    tree = tree_result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "TaskTree not found")

    from agentid.worker.task_tree_worker import _process_tree

    assigned, skipped = await _process_tree(db, tree)
    await db.commit()

    return {
        "tree_id": tree_id,
        "assigned": assigned,
        "skipped": skipped,
        "message": f"Processed tree {tree_id[:8]}: {assigned} assigned, {skipped} skipped",
    }


@router.post("/{tree_id}/settle", response_model=SettleResponse)
async def settle_tree(
    tree_id: str,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db),
):
    """
    Settle and distribute rewards for a completed or partial tree.
    Only agents with status='completed' receive rewards.
    """
    tree_result = await db.execute(select(TaskTree).where(TaskTree.id == tree_id))
    tree = tree_result.scalar_one_or_none()
    if not tree:
        raise HTTPException(404, "TaskTree not found")

    if tree.status not in ("completed", "partial"):
        raise HTTPException(422, f"Tree status is '{tree.status}', must be 'completed' or 'partial' to settle")

    nodes_result = await db.execute(select(TaskNode).where(TaskNode.tree_id == tree_id))
    nodes = nodes_result.scalars().all()

    total_reward = tree.total_reward or 0.0
    settlements = []
    settled = 0
    skipped = 0

    for node in nodes:
        if node.status != "completed" or not node.assigned_agent_did:
            skipped += 1
            continue

        payout = round(total_reward * node.reward_fraction, 4)
        settlements.append({
            "node_id": node.id,
            "agent_did": node.assigned_agent_did,
            "reward_fraction": node.reward_fraction,
            "payout": payout,
            "domain": node.domain,
            "title": node.title,
        })
        settled += 1

    return SettleResponse(
        tree_id=tree_id,
        total_reward=total_reward,
        settlements=settlements,
        settled_count=settled,
        skipped_count=skipped,
    )