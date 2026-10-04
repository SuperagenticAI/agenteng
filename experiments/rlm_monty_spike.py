"""Model-free RLM execution spike using real Monty 1.0 sessions.

Run with an interpreter that has pydantic-monty==1.0.0 installed.
Scripted programs stand in for model responses: this checks execution mechanics,
not language-model quality, token cost, provider integration or production safety.
The corpus is synthetic and makes no claims about actual conference content.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from typing import Any

from pydantic_monty import Monty


CORPUS = {
    "demo-memory": "A synthetic session discusses durable memory and retrieval.",
    "demo-evals": "A synthetic session discusses evaluation and regression checks.",
}

PREAMBLE = """
class Context:
    def read(self, source_id):
        return _read(source_id)

class Recursion:
    def run(self, question, source_ids):
        return _delegate(question, source_ids)

def llm_query(question, source_ids):
    return _leaf(question, source_ids)

ctx = Context()
rlm = Recursion()
"""

# Each list represents successive run_code calls in one reasoning session.
PROGRAMS = {
    "compare": [
        "finding = rlm.run('extract', source_ids)",
        "{'findings': [finding], 'source_ids': source_ids}",
    ],
    "extract": [
        "{'texts': [ctx.read(sid) for sid in source_ids], 'source_ids': source_ids}"
    ],
    "state": ["value = 40", "value + 2"],
    "deep": ["rlm.run('deep', source_ids)"],
    "scope_attack": ["rlm.run('extract', ['demo-evals'])"],
    "read_attack": ["ctx.read('demo-evals')"],
    "filesystem_attack": ["open('/etc/passwd').read()"],
    "environment_attack": ["import os\nos.environ"],
    "invented_citation": ["{'source_ids': ['missing-source']}"],
    "two_children": ["rlm.run('extract', source_ids)", "rlm.run('extract', source_ids)"],
    "leaf_only": ["llm_query('extract', source_ids)"],
    "child_leaf": ["rlm.run('leaf_only', source_ids)"],
    "child_then_leaf": ["rlm.run('extract', source_ids)", "llm_query('extract', source_ids)"],
    "leaf_then_child": ["llm_query('extract', source_ids)", "rlm.run('extract', source_ids)"],
    "failed_child": ["raise ValueError('Scripted child failure')"],
    "retry_child": [
        "try:\n    rlm.run('failed_child', source_ids)\n"
        "except Exception:\n    rlm.run('extract', source_ids)"
    ],
}


@dataclass
class SpikeRuntime:
    pool: Any
    admitted: int = 0
    delegations: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)

    def run(self, question: str, source_ids: list[str]) -> Any:
        return self._run(question, source_ids, depth=0)

    def _run(self, question: str, source_ids: list[str], depth: int) -> Any:
        scope = frozenset(source_ids)
        if not scope or not scope <= CORPUS.keys():
            raise ValueError("Unknown or empty source scope")
        if depth > 1:
            raise ValueError("Tree depth exhausted")
        if self.admitted >= 2:
            raise ValueError("Shared tree node budget exhausted")
        steps = PROGRAMS[question]
        self.admitted += 1
        self.trace.append({"depth": depth, "question": question, "scope": sorted(scope)})

        def read(source_id: str) -> str:
            if source_id not in scope:
                raise ValueError("Read outside delegated scope")
            return CORPUS[source_id]

        def reserve(child_sources: list[str]) -> None:
            if depth >= 1:
                raise ValueError("Tree depth exhausted")
            if not frozenset(child_sources) <= scope:
                raise ValueError("Child attempted to widen source scope")
            if self.delegations >= 1:
                raise ValueError("Single delegation allowance exhausted")
            # Consume admission before execution; failed calls cannot be retried.
            self.delegations += 1

        def delegate(child_question: str, child_sources: list[str]) -> Any:
            reserve(child_sources)
            return self._run(child_question, child_sources, depth + 1)

        def leaf(child_question: str, child_sources: list[str]) -> Any:
            reserve(child_sources)
            if child_question != "extract" or not child_sources:
                raise ValueError("Unsupported scripted leaf request")
            return {"texts": [read(sid) for sid in child_sources], "source_ids": child_sources}

        with self.pool.checkout(
            limits={
                "max_memory": 8 * 1024 * 1024,
                "max_feed_duration_secs": 1.0,
                "max_suspensions": 32,
            }
        ) as session:
            externals = {"_read": read, "_delegate": delegate, "_leaf": leaf}
            session.feed_run(PREAMBLE)
            session.feed_run("source_ids = delegated_ids", inputs={"delegated_ids": sorted(scope)})
            result = None
            for code in steps:
                result = session.feed_run(code, external_lookup=externals)

        self.validate_sources(result, scope)
        return result

    @classmethod
    def validate_sources(cls, value: Any, scope: frozenset[str]) -> None:
        """Check reference membership; this does not establish claim truth."""
        if isinstance(value, dict):
            if "source_ids" in value and not frozenset(value["source_ids"]) <= scope:
                raise ValueError("Result cites evidence outside its source scope")
            for item in value.values():
                cls.validate_sources(item, scope)
        elif isinstance(value, list):
            for item in value:
                cls.validate_sources(item, scope)


class MontyRecursionChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # A suspended parent retains its worker. Two workers allow root and
        # one child; one worker would stall a blocking callback.
        cls.pool = Monty(max_processes=2, checkout_timeout=2.0, request_timeout=5.0)
        cls.pool.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.pool.__exit__(None, None, None)

    def test_root_single_child_and_sources(self) -> None:
        runtime = SpikeRuntime(self.pool)
        result = runtime.run("compare", list(CORPUS))
        self.assertEqual(runtime.admitted, 2)
        self.assertEqual(runtime.delegations, 1)
        self.assertEqual([node["depth"] for node in runtime.trace], [0, 1])
        self.assertEqual(result["source_ids"], sorted(CORPUS))
        for finding in result["findings"]:
            self.assertEqual(finding["texts"], [CORPUS[sid] for sid in finding["source_ids"]])

    def test_variables_persist_between_code_calls(self) -> None:
        self.assertEqual(SpikeRuntime(self.pool).run("state", ["demo-memory"]), 42)

    def test_child_cannot_widen_scope(self) -> None:
        with self.assertRaisesRegex(Exception, "widen source scope"):
            SpikeRuntime(self.pool).run("scope_attack", ["demo-memory"])

    def test_read_scope_is_enforced(self) -> None:
        with self.assertRaisesRegex(Exception, "outside delegated scope"):
            SpikeRuntime(self.pool).run("read_attack", ["demo-memory"])

    def test_depth_is_bounded(self) -> None:
        runtime = SpikeRuntime(self.pool)
        with self.assertRaisesRegex(Exception, "Tree depth exhausted"):
            runtime.run("deep", ["demo-memory"])
        self.assertEqual(runtime.admitted, 2)
        self.assertEqual(runtime.delegations, 1)

    def test_second_child_is_rejected(self) -> None:
        runtime = SpikeRuntime(self.pool)
        with self.assertRaisesRegex(Exception, "Single delegation allowance exhausted"):
            runtime.run("two_children", list(CORPUS))
        self.assertEqual(runtime.admitted, 2)

    def test_leaf_call_consumes_the_allowance(self) -> None:
        runtime = SpikeRuntime(self.pool)
        self.assertEqual(runtime.run("leaf_only", ["demo-memory"])["texts"], [CORPUS["demo-memory"]])
        self.assertEqual(runtime.delegations, 1)
        self.assertEqual(runtime.admitted, 1)

    def test_child_cannot_make_a_leaf_call(self) -> None:
        runtime = SpikeRuntime(self.pool)
        with self.assertRaisesRegex(Exception, "Tree depth exhausted"):
            runtime.run("child_leaf", ["demo-memory"])
        self.assertEqual(runtime.delegations, 1)
        self.assertEqual(runtime.admitted, 2)

    def test_child_then_leaf_is_rejected(self) -> None:
        with self.assertRaisesRegex(Exception, "Single delegation allowance exhausted"):
            SpikeRuntime(self.pool).run("child_then_leaf", ["demo-memory"])

    def test_leaf_then_child_is_rejected(self) -> None:
        with self.assertRaisesRegex(Exception, "Single delegation allowance exhausted"):
            SpikeRuntime(self.pool).run("leaf_then_child", ["demo-memory"])

    def test_failed_child_does_not_refund_the_allowance(self) -> None:
        runtime = SpikeRuntime(self.pool)
        with self.assertRaisesRegex(Exception, "Single delegation allowance exhausted"):
            runtime.run("retry_child", ["demo-memory"])
        self.assertEqual(runtime.delegations, 1)

    def test_filesystem_is_not_exposed(self) -> None:
        with self.assertRaises(Exception):
            SpikeRuntime(self.pool).run("filesystem_attack", ["demo-memory"])

    def test_environment_is_not_exposed(self) -> None:
        with self.assertRaises(Exception):
            SpikeRuntime(self.pool).run("environment_attack", ["demo-memory"])

    def test_invented_citations_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside its source scope"):
            SpikeRuntime(self.pool).run("invented_citation", ["demo-memory"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
