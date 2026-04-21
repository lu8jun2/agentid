"""LLM-based task decomposition service — converts a task into a DAG of TaskNodes."""
import os, json, uuid
from datetime import datetime
from typing import TypedDict
import anthropic
from agentid.config import settings

# ── Prompt Template ────────────────────────────────────────────────────────────

DECOMPOSE_PROMPT = '''你是一个专业的任务规划助手。请将以下大任务拆解成微任务有向无环图（DAG）。

任务：{description}
领域：{domain_hint}
Token 预算：约 {max_tokens} tokens
赏金：${reward}

要求：
1. 拆解成 4-10 个子任务，每个子任务应可独立执行
2. 标注每个子任务的领域（coding/writing/research/data/creative/devops/general）
3. 预估每个子任务的 token 消耗和执行时间（分钟）
4. 分配赏金比例（总和=1.0，精确到小数点后2位）
5. 标注父子依赖关系（root 节点 parent_ids 为空）
6. 提供每个节点的执行指导（guidance）

输出格式（只输出 JSON，不要有其他内容）：
{{
  "nodes": [
    {{
      "title": "子任务标题（50字以内）",
      "description": "具体描述（100字以内）",
      "domain": "coding",
      "parent_ids": ["parent_uuid 或 null 表示根节点"],
      "estimated_tokens": 2000,
      "estimated_minutes": 15,
      "reward_fraction": 0.15,
      "guidance": "给执行 agent 的具体指令（100字以内）"
    }}
  ]
}}'''

# ── Typed output ──────────────────────────────────────────────────────────────

class DecomposedNode(TypedDict):
    title: str
    description: str
    domain: str
    parent_ids: list[str]
    estimated_tokens: int
    estimated_minutes: int
    reward_fraction: float
    guidance: str


class DecompositionResult(TypedDict):
    nodes: list[DecomposedNode]
    raw_response: str


# ── Client ────────────────────────────────────────────────────────────────────

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY or CLAUDE_API_KEY environment variable not set")
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def decompose_task(
    description: str,
    domain_hint: str = "general",
    max_tokens: int = 6000,
    reward: float = 0.0,
    model: str = "claude-sonnet-4-7",
) -> DecompositionResult:
    """
    Call Claude to decompose a task into a DAG.

    Raises:
        RuntimeError: if the API key is missing or the response is malformed.
    """
    prompt = DECOMPOSE_PROMPT.format(
        description=description,
        domain_hint=domain_hint,
        max_tokens=max_tokens,
        reward=reward,
    )

    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if raw.endswith("```"):
            raw = raw[:-3].strip()

    parsed = json.loads(raw)

    nodes: list[DecomposedNode] = []
    for n in parsed.get("nodes", []):
        nodes.append({
            "title": str(n["title"])[:200],
            "description": str(n.get("description", ""))[:500],
            "domain": str(n.get("domain", "general"))[:64],
            "parent_ids": [str(pid) for pid in n.get("parent_ids", [])],
            "estimated_tokens": int(n.get("estimated_tokens", 0)),
            "estimated_minutes": int(n.get("estimated_minutes", 0)),
            "reward_fraction": round(float(n.get("reward_fraction", 0.0)), 4),
            "guidance": str(n.get("guidance", ""))[:1000],
        })

    # Validate: root nodes must have empty parent_ids
    root_nodes = [n for n in nodes if not n["parent_ids"]]
    if not root_nodes:
        raise RuntimeError("LLM decomposition returned no root node (no node with empty parent_ids)")

    return DecompositionResult(nodes=nodes, raw_response=raw)
