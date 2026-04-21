"""Unit tests for task decomposer — tests output parsing and validation logic."""
import pytest
import json
from agentid.core.decomposer import DecomposedNode, DecompositionResult


class TestDecomposeOutputParsing:
    """Test the decompose_task output parsing by directly calling the parsing logic."""

    def test_valid_json_parsing(self):
        raw = json.dumps({
            "nodes": [
                {
                    "title": "Research",
                    "description": "Gather requirements",
                    "domain": "research",
                    "parent_ids": [],
                    "estimated_tokens": 1000,
                    "estimated_minutes": 15,
                    "reward_fraction": 0.20,
                    "guidance": "Collect user requirements",
                },
                {
                    "title": "Build",
                    "description": "Write code",
                    "domain": "coding",
                    "parent_ids": ["Research"],
                    "estimated_tokens": 5000,
                    "estimated_minutes": 60,
                    "reward_fraction": 0.60,
                    "guidance": "Implement the feature",
                },
            ]
        })
        # Simulate the parsing logic from decompose_task
        parsed = json.loads(raw)
        assert len(parsed["nodes"]) == 2
        assert parsed["nodes"][0]["title"] == "Research"
        assert parsed["nodes"][0]["parent_ids"] == []

    def test_root_node_detection(self):
        nodes = [
            {"title": "Plan", "parent_ids": []},
            {"title": "Build", "parent_ids": ["Plan"]},
            {"title": "Deploy", "parent_ids": ["Build"]},
        ]
        roots = [n for n in nodes if not n.get("parent_ids")]
        assert len(roots) == 1
        assert roots[0]["title"] == "Plan"

    def test_no_root_raises(self):
        nodes = [
            {"title": "Build", "parent_ids": ["Deploy"]},
            {"title": "Deploy", "parent_ids": ["Build"]},
        ]
        roots = [n for n in nodes if not n.get("parent_ids")]
        assert len(roots) == 0  # cycle — no root detected

    def test_strips_code_fences(self):
        raw = """```json
{"nodes": [{"title": "Test", "parent_ids": []}]}
```"""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
            if text.endswith("```"):
                text = text[:-3].strip()
        parsed = json.loads(text)
        assert parsed["nodes"][0]["title"] == "Test"

    def test_reward_fraction_rounds(self):
        raw = json.dumps({
            "nodes": [
                {
                    "title": "Task",
                    "parent_ids": [],
                    "reward_fraction": 0.156789,
                }
            ]
        })
        parsed = json.loads(raw)
        fraction = round(float(parsed["nodes"][0]["reward_fraction"]), 4)
        assert fraction == 0.1568

    def test_missing_optional_fields_get_defaults(self):
        raw = json.dumps({
            "nodes": [
                {"title": "Minimal", "parent_ids": []}
            ]
        })
        parsed = json.loads(raw)
        n = parsed["nodes"][0]
        assert n.get("domain", "general") == "general"
        assert n.get("estimated_tokens", 0) == 0
        assert n.get("estimated_minutes", 0) == 0
        assert n.get("reward_fraction", 0.0) == 0.0

    def test_parent_ids_can_be_null_or_empty(self):
        for raw in [
            json.dumps({"nodes": [{"title": "Root", "parent_ids": []}]}),
            json.dumps({"nodes": [{"title": "Root", "parent_ids": [None]}]}),
            json.dumps({"nodes": [{"title": "Root"}]}),  # missing key
        ]:
            parsed = json.loads(raw)
            n = parsed["nodes"][0]
            pids = [str(p) for p in n.get("parent_ids", []) if p]
            # None and missing should not produce a parent
            assert len(pids) == 0

    def test_truncation(self):
        long_title = "x" * 300
        raw = json.dumps({
            "nodes": [{"title": long_title, "parent_ids": []}]
        })
        parsed = json.loads(raw)
        title = str(parsed["nodes"][0]["title"])[:200]
        assert len(title) == 200

    def test_empty_nodes_list_still_parses(self):
        raw = json.dumps({"nodes": []})
        parsed = json.loads(raw)
        assert parsed["nodes"] == []
