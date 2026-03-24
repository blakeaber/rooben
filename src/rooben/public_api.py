"""
Rooben Public API Surface
===========================

This module re-exports the stable extension points of the rooben framework.
Third-party packages (e.g., ``rooben-pro``) should depend on these protocols
and models — not on internal implementation details.

Protocols (implement these to extend rooben):

    - ``LLMProvider``    — plug in any LLM backend
    - ``StateBackend``   — plug in any persistence layer
    - ``Verifier``       — plug in any verification strategy
    - ``Planner``        — plug in any task decomposition strategy
    - ``AgentProtocol``  — plug in any agent execution backend
    - ``LearningStoreProtocol`` — plug in any learning persistence

Models (use these as inputs/outputs):

    - ``Specification``  — the validated project schema
    - ``GenerationResult`` — LLM response with token usage
    - ``WorkflowState``  — runtime state of a workflow
    - ``Task``, ``TaskResult``, ``TokenUsage`` — core domain objects
    - ``VerificationResult`` — outcome of task verification

Orchestrator:

    - ``Orchestrator``   — the main execution engine (accepts all protocols above)

Usage::

    from rooben.public_api import LLMProvider, GenerationResult

    class MyProvider:
        async def generate(self, system, prompt, max_tokens=4096):
            ...  # your implementation
        async def generate_multi(self, system, messages, max_tokens=4096):
            ...  # your implementation
"""

from __future__ import annotations

API_VERSION = "0.1.0"

# ── Protocols ──────────────────────────────────────────────────────────

from rooben.agents.protocol import AgentProtocol  # noqa: E402
from rooben.memory.protocol import LearningStoreProtocol  # noqa: E402
from rooben.planning.planner import Planner  # noqa: E402
from rooben.planning.provider import LLMProvider  # noqa: E402
from rooben.state.protocol import StateBackend  # noqa: E402
from rooben.verification.verifier import Verifier  # noqa: E402

# ── Models ─────────────────────────────────────────────────────────────

from rooben.domain import Task, TaskResult, TokenUsage, WorkflowState  # noqa: E402
from rooben.planning.provider import GenerationResult  # noqa: E402
from rooben.spec.models import Specification  # noqa: E402
from rooben.verification.verifier import VerificationResult  # noqa: E402

# ── Orchestrator ───────────────────────────────────────────────────────

from rooben.orchestrator import Orchestrator  # noqa: E402

# ── Built-in implementations (convenience re-exports) ─────────────────

from rooben.planning.provider import AnthropicProvider  # noqa: E402
from rooben.state.filesystem import FilesystemBackend  # noqa: E402
from rooben.verification.llm_judge import LLMJudgeVerifier  # noqa: E402

__all__ = [
    "API_VERSION",
    # Protocols
    "LLMProvider",
    "StateBackend",
    "Verifier",
    "Planner",
    "AgentProtocol",
    "LearningStoreProtocol",
    # Models
    "Specification",
    "GenerationResult",
    "WorkflowState",
    "Task",
    "TaskResult",
    "TokenUsage",
    "VerificationResult",
    # Orchestrator
    "Orchestrator",
    # Built-in implementations
    "AnthropicProvider",
    "FilesystemBackend",
    "LLMJudgeVerifier",
]
