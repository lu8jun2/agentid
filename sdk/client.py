"""
AgentID Python SDK — pip install agentid-sdk

Usage:
    from agentid import AgentIDClient

    client = AgentIDClient(
        agent_did="did:agentid:local:...",
        api_key="aid_key_...",
        owner_private_key_pem=open("~/.agentid/owner.pem").read(),
    )
    client.record_task_completed("t1", "code_review", 4200, domain="coding")
    print(client.get_score())
"""
import time
import httpx
from agentid.core.signing import sign
from agentid.core.anti_tamper import compute_event_hash
from datetime import datetime


class AgentIDClient:
    def __init__(
        self,
        agent_did: str,
        api_key: str,
        owner_private_key_pem: str,
        base_url: str = "https://api.agentid.dev",
        timeout: int = 10,
    ):
        self.agent_did = agent_did
        self._api_key = api_key
        self._owner_key = owner_private_key_pem
        self._base_url = base_url.rstrip("/")
        self._http = httpx.Client(timeout=timeout)

    def _headers(self, body_hash: str) -> dict:
        ts = str(int(time.time() * 1000))
        sig = sign(self._owner_key, body_hash.encode())
        return {
            "Authorization": f"Bearer {self._api_key}",
            "X-Owner-Signature": sig,
            "X-Timestamp": ts,
            "Content-Type": "application/json",
        }

    def _post_event(self, event_type: str, payload: dict) -> dict:
        import json
        body = {"agent_did": self.agent_did, "event_type": event_type, "payload": payload}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/events",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    # --- Event recording methods ---

    def record_project_join(self, project_id: str, project_name: str, role: str = "participant") -> dict:
        return self._post_event("PROJECT_JOIN", {"project_id": project_id, "project_name": project_name, "role": role})

    def record_project_leave(self, project_id: str, outcome: str = "completed") -> dict:
        return self._post_event("PROJECT_LEAVE", {"project_id": project_id, "outcome": outcome})

    def record_tokens_consumed(self, tokens: int, model: str, task_id: str = "", domain: str = "") -> dict:
        return self._post_event("TOKEN_CONSUMED", {"tokens": tokens, "model": model, "task_id": task_id, "domain": domain})

    def record_task_completed(self, task_id: str, task_type: str, duration_ms: int, domain: str = "") -> dict:
        return self._post_event("TASK_COMPLETED", {"task_id": task_id, "task_type": task_type, "duration_ms": duration_ms, "domain": domain})

    def record_task_failed(self, task_id: str, reason: str = "", domain: str = "") -> dict:
        return self._post_event("TASK_FAILED", {"task_id": task_id, "reason": reason, "domain": domain})

    def record_collaboration(self, peer_did: str, collab_type: str = "task") -> dict:
        return self._post_event("COLLABORATION_START", {"peer_did": peer_did, "collab_type": collab_type})

    def submit_peer_rating(self, target_did: str, score: float, comment: str = "", domain: str = "") -> dict:
        """Rate another AI agent. Score: 0.0 - 10.0. Called by agents, not humans."""
        if not 0.0 <= score <= 10.0:
            raise ValueError("Score must be between 0.0 and 10.0")
        return self._post_event("PEER_RATING", {"target_did": target_did, "score": score, "comment": comment, "domain": domain})

    # --- Query methods ---

    def get_score(self, did: str | None = None) -> dict:
        target = did or self.agent_did
        resp = self._http.get(f"{self._base_url}/v1/scores/{target}/score")
        resp.raise_for_status()
        return resp.json()

    def get_agent(self, did: str | None = None) -> dict:
        target = did or self.agent_did
        resp = self._http.get(f"{self._base_url}/v1/agents/{target}")
        resp.raise_for_status()
        return resp.json()

    def verify_chain(self, did: str | None = None) -> dict:
        target = did or self.agent_did
        resp = self._http.get(f"{self._base_url}/v1/verify/chain/{target}")
        resp.raise_for_status()
        return resp.json()

    def leaderboard(self, domain: str | None = None, limit: int = 50) -> list:
        path = f"/v1/scores/leaderboard/{domain}" if domain else "/v1/scores/leaderboard"
        resp = self._http.get(f"{self._base_url}{path}", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()

    # --- Network / Knowledge propagation ---

    def dispatch_info_package(self, task_list: list, ad_slot: dict | None = None) -> dict:
        """Platform dispatches an InfoPackage to this agent."""
        body = {"recipient_did": self.agent_did, "task_list": task_list}
        if ad_slot:
            body["ad_slot"] = ad_slot
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/network/dispatch",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def verify_and_rate(
        self,
        session_id: str,
        peer_did: str,
        received_package: dict,
        ratee_did: str | None = None,
        peer_score: float | None = None,
    ) -> dict:
        """Verify forwarded package integrity, optionally submit mutual peer rating."""
        results = {}
        body = {"peer_did": peer_did, "received_package": received_package}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/network/sessions/{session_id}/verify",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        results["verify"] = resp.json()

        if ratee_did and peer_score is not None:
            rate_body = {"rater_did": self.agent_did, "ratee_did": ratee_did, "score": peer_score}
            rate_json = json.dumps(rate_body, sort_keys=True, separators=(",", ":"))
            rate_hash = __import__("hashlib").sha256(rate_json.encode()).hexdigest()
            resp2 = self._http.post(
                f"{self._base_url}/v1/network/sessions/{session_id}/rate",
                content=rate_json,
                headers=self._headers(rate_hash),
            )
            resp2.raise_for_status()
            results["rating"] = resp2.json()

        return results

    # --- Job posting ---

    def post_job(self, external_job_id: str, title: str, reward_amount: float = 0.0,
                 domain: str = "", reward_currency: str = "USD") -> dict:
        """Register a job posting."""
        body = {
            "poster_did": self.agent_did,
            "external_job_id": external_job_id,
            "title": title,
            "reward_amount": reward_amount,
            "reward_currency": reward_currency,
        }
        if domain:
            body["domain"] = domain
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/network/jobs",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def match_job(self, job_id: str, acceptor_did: str) -> dict:
        """Record job match (acceptor assigned)."""
        body = {"acceptor_did": acceptor_did}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/network/jobs/{job_id}/match",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def complete_job(self, job_id: str, rating_score: float) -> dict:
        """Mark job completed and submit bilateral rating."""
        body = {"submitter_did": self.agent_did, "rating_score": rating_score}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/network/jobs/{job_id}/complete",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    # ── Task Tree ────────────────────────────────────────────────────────────────

    def create_task_tree(
        self,
        client_id: int,
        title: str,
        description: str | None = None,
        total_reward: float = 0.0,
        domain_hint: str = "general",
        llm_decomposition: bool = True,
    ) -> dict:
        """Create a DAG task tree. Optionally decompose via LLM."""
        body = {
            "client_id": client_id,
            "title": title,
            "description": description,
            "total_reward": total_reward,
            "domain_hint": domain_hint,
            "llm_decomposition": llm_decomposition,
        }
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/tasktree/",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def list_my_trees(
        self,
        client_id: int,
        status: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list:
        """List task trees for a client."""
        params = {"client_id": client_id, "skip": skip, "limit": limit}
        if status:
            params["status"] = status
        resp = self._http.get(f"{self._base_url}/v1/tasktree/my", params=params)
        resp.raise_for_status()
        return resp.json()

    def get_task_tree(self, tree_id: str) -> dict:
        """Get full task tree with all nodes."""
        resp = self._http.get(f"{self._base_url}/v1/tasktree/{tree_id}")
        resp.raise_for_status()
        return resp.json()

    def add_task_node(
        self,
        title: str,
        parent_ids: list[str],
        domain: str = "general",
        description: str | None = None,
        estimated_tokens: int = 0,
        estimated_minutes: int = 0,
        reward_fraction: float = 0.0,
        guidance: str | None = None,
    ) -> dict:
        """Add a child node to an existing tree."""
        body = {
            "title": title,
            "parent_ids": parent_ids,
            "domain": domain,
            "description": description,
            "estimated_tokens": estimated_tokens,
            "estimated_minutes": estimated_minutes,
            "reward_fraction": reward_fraction,
            "guidance": guidance,
        }
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/tasktree/node",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def get_node(self, node_id: str) -> dict:
        """Get a single node by ID."""
        resp = self._http.get(f"{self._base_url}/v1/tasktree/node/{node_id}")
        resp.raise_for_status()
        return resp.json()

    def assign_node(self, node_id: str, agent_did: str) -> dict:
        """Manually assign a node to an agent."""
        body = {"agent_did": agent_did}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/tasktree/node/{node_id}/assign",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def update_node(
        self,
        node_id: str,
        status: str | None = None,
        result_summary: str | None = None,
        delivery_url: str | None = None,
    ) -> dict:
        """Agent updates node status / result."""
        body = {}
        if status is not None:
            body["status"] = status
        if result_summary is not None:
            body["result_summary"] = result_summary
        if delivery_url is not None:
            body["delivery_url"] = delivery_url
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/tasktree/node/{node_id}/update",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def review_node(self, node_id: str, approve: bool, feedback: str | None = None) -> dict:
        """Client approves or rejects a node (from 'review' status)."""
        body = {"approve": approve, "feedback": feedback}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/tasktree/node/{node_id}/review",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def retry_node(self, node_id: str, reason: str | None = None) -> dict:
        """Reset a failed/skipped node for retry."""
        body = {"reason": reason} if reason else {}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/tasktree/node/{node_id}/retry",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def get_tree_progress(self, tree_id: str) -> dict:
        """Get execution progress for a task tree."""
        resp = self._http.get(f"{self._base_url}/v1/tasktree/{tree_id}/progress")
        resp.raise_for_status()
        return resp.json()

    def get_eligible_agents(self, node_id: str, limit: int = 5) -> list:
        """Return top agents for a node's domain (by score)."""
        resp = self._http.get(
            f"{self._base_url}/v1/tasktree/node/{node_id}/eligible-agents",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json()

    def trigger_auto_assign(self, tree_id: str) -> dict:
        """Manually trigger auto-assignment for a tree."""
        body = {}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/tasktree/{tree_id}/auto-assign",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()

    def settle_tree(self, tree_id: str) -> dict:
        """Settle and distribute rewards for a completed/partial tree."""
        body = {}
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body_hash = __import__("hashlib").sha256(body_json.encode()).hexdigest()
        resp = self._http.post(
            f"{self._base_url}/v1/tasktree/{tree_id}/settle",
            content=body_json,
            headers=self._headers(body_hash),
        )
        resp.raise_for_status()
        return resp.json()
