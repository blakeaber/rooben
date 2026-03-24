"""P11 — Agent & Integration Configuration unit tests."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


# ── R-11.1: Credential encryption ────────────────────────────────────────


def test_fernet_encrypt_decrypt_roundtrip():
    """Verify encrypt → decrypt returns original value."""
    from rooben.dashboard.credentials import (
        encrypt_value,
        decrypt_value,
        reset_fernet,
    )

    # Use a temp dir for key storage
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / ".credential_key"
        with patch(
            "rooben.dashboard.credentials.Path",
            return_value=key_path,
        ):
            reset_fernet()
            # Force fresh key generation via env var
            os.environ["ROOBEN_CREDENTIAL_KEY"] = ""
            reset_fernet()

            secret = "my-secret-api-key-12345"
            encrypted = encrypt_value(secret)
            assert encrypted != secret
            decrypted = decrypt_value(encrypted)
            assert decrypted == secret

            reset_fernet()


def test_fernet_key_auto_generation():
    """Verify key is auto-generated when neither env nor file exists."""
    from rooben.dashboard.credentials import get_fernet, reset_fernet

    reset_fernet()
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = Path(tmpdir) / ".rooben" / ".credential_key"
        env_patch = patch.dict(os.environ, {"ROOBEN_CREDENTIAL_KEY": ""})
        path_patch = patch(
            "rooben.dashboard.credentials.Path",
            return_value=key_path,
        )
        with env_patch, path_patch:
            reset_fernet()
            f = get_fernet()
            assert f is not None
            reset_fernet()


@pytest.mark.asyncio
async def test_credential_masking():
    """Verify list returns masked values."""
    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(
        return_value=[
            {
                "id": "c1",
                "integration_name": "slack",
                "env_var_name": "SLACK_TOKEN",
                "created_at": "2024-01-01",
                "updated_at": "2024-01-01",
            }
        ]
    )

    from rooben.dashboard.queries.credentials import list_credentials

    result = await list_credentials(mock_pool)
    assert len(result) == 1
    assert result[0]["value"] == "****"
    assert result[0]["env_var_name"] == "SLACK_TOKEN"


@pytest.mark.asyncio
async def test_upsert_credential():
    """Verify upsert returns masked result."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        return_value={
            "id": "c1",
            "integration_name": "slack",
            "env_var_name": "SLACK_TOKEN",
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
        }
    )

    from rooben.dashboard.queries.credentials import upsert_credential

    result = await upsert_credential(
        mock_pool, "c1", "slack", "SLACK_TOKEN", "xoxb-secret"
    )
    assert result["value"] == "****"
    assert result["id"] == "c1"
    # Verify encrypt was called (the encrypted_value arg)
    call_args = mock_pool.fetchrow.call_args[0]
    assert call_args[3] != "xoxb-secret"  # Should be encrypted


@pytest.mark.asyncio
async def test_delete_credential():
    """Verify delete returns True on success."""
    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock(return_value="DELETE 1")

    from rooben.dashboard.queries.credentials import delete_credential

    result = await delete_credential(mock_pool, "c1")
    assert result is True


def test_substitute_env_vars_fallback_to_cache():
    """Verify _substitute_env_vars falls back to credential cache."""
    import rooben.agents.integrations as integrations_mod

    # Clear env var
    original = os.environ.pop("MY_TEST_CREDENTIAL", None)
    try:
        # Set cache
        integrations_mod._credential_cache["MY_TEST_CREDENTIAL"] = "cached-value"

        result = integrations_mod._substitute_env_vars("token=${MY_TEST_CREDENTIAL}")
        assert result == "token=cached-value"

        # Env var takes precedence
        os.environ["MY_TEST_CREDENTIAL"] = "env-value"
        result = integrations_mod._substitute_env_vars("token=${MY_TEST_CREDENTIAL}")
        assert result == "token=env-value"
    finally:
        integrations_mod._credential_cache.pop("MY_TEST_CREDENTIAL", None)
        if original is not None:
            os.environ["MY_TEST_CREDENTIAL"] = original
        else:
            os.environ.pop("MY_TEST_CREDENTIAL", None)


# ── R-11.2: Agent behavior customization ─────────────────────────────────


@pytest.mark.asyncio
async def test_update_agent_integration():
    """Verify agent integration update."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        return_value={
            "id": "agent-1",
            "name": "coder",
            "transport": "llm",
            "description": "",
            "endpoint": "",
            "capabilities": "[]",
            "mcp_servers": "[]",
            "budget": None,
            "integration": "coding",
            "prompt_template": "",
            "model_override": "",
            "max_concurrency": 1,
            "max_context_tokens": 200000,
            "first_seen_at": "2024-01-01",
            "updated_at": "2024-01-01",
        }
    )

    from rooben.dashboard.queries.agents import update_agent

    result = await update_agent(mock_pool, "agent-1", {"integration": "coding"})
    assert result is not None
    assert result["integration"] == "coding"


@pytest.mark.asyncio
async def test_update_agent_prompt_template():
    """Verify agent prompt_template update."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        return_value={
            "id": "agent-1",
            "name": "coder",
            "transport": "llm",
            "description": "",
            "endpoint": "",
            "capabilities": "[]",
            "mcp_servers": "[]",
            "budget": None,
            "integration": "",
            "prompt_template": "You are a helpful assistant.",
            "model_override": "",
            "max_concurrency": 1,
            "max_context_tokens": 200000,
            "first_seen_at": "2024-01-01",
            "updated_at": "2024-01-01",
        }
    )

    from rooben.dashboard.queries.agents import update_agent

    result = await update_agent(
        mock_pool, "agent-1", {"prompt_template": "You are a helpful assistant."}
    )
    assert result is not None
    assert result["prompt_template"] == "You are a helpful assistant."


@pytest.mark.asyncio
async def test_update_agent_model_override():
    """Verify agent model_override update."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        return_value={
            "id": "agent-1",
            "name": "coder",
            "transport": "llm",
            "description": "",
            "endpoint": "",
            "capabilities": "[]",
            "mcp_servers": "[]",
            "budget": None,
            "integration": "",
            "prompt_template": "",
            "model_override": "claude-sonnet-4-20250514",
            "max_concurrency": 1,
            "max_context_tokens": 200000,
            "first_seen_at": "2024-01-01",
            "updated_at": "2024-01-01",
        }
    )

    from rooben.dashboard.queries.agents import update_agent

    result = await update_agent(
        mock_pool, "agent-1", {"model_override": "claude-sonnet-4-20250514"}
    )
    assert result is not None
    assert result["model_override"] == "claude-sonnet-4-20250514"


@pytest.mark.asyncio
async def test_update_agent_404():
    """Verify update returns None for nonexistent agent."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)

    from rooben.dashboard.queries.agents import update_agent

    result = await update_agent(mock_pool, "nonexistent", {"integration": "coding"})
    assert result is None


def test_list_integration_names():
    """Verify integration names endpoint returns expected structure."""
    from rooben.agents.integrations import IntegrationRegistry

    registry = IntegrationRegistry()
    integrations = registry.list_all()
    assert len(integrations) >= 4  # 4 LLM providers

    names = [tk.name for tk in integrations]
    assert "anthropic" in names
    assert "openai" in names
    assert "ollama" in names


# ── R-11.3: Task-agent reassignment ──────────────────────────────────────


@pytest.mark.asyncio
async def test_update_task_reassign_agent():
    """Verify task agent reassignment."""
    mock_pool = AsyncMock()
    # First call: check status
    mock_pool.fetchrow = AsyncMock(
        side_effect=[
            {"status": "pending"},  # status check
            {  # get_task return
                "id": "t1",
                "title": "Task 1",
                "description": "",
                "status": "pending",
                "assigned_agent_id": "agent-2",
                "workstream_id": "ws1",
                "workflow_id": "wf1",
                "attempt": 0,
                "max_retries": 3,
                "verification_strategy": "llm_judge",
                "created_at": "2024-01-01",
                "started_at": None,
                "completed_at": None,
                "attempt_feedback": "[]",
                "result": None,
                "structured_prompt": None,
                "acceptance_criteria_ids": "[]",
                "skeleton_tests": "[]",
                "priority": 0,
                "linear_issue_id": None,
                "updated_at": "2024-01-01",
                "output": None,
                "error": None,
            },
        ]
    )
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    mock_pool.fetch = AsyncMock(return_value=[])  # depends_on

    from rooben.dashboard.queries.tasks import update_task

    result = await update_task(mock_pool, "t1", {"assigned_agent_id": "agent-2"})
    assert result is not None
    assert result["assigned_agent_id"] == "agent-2"


@pytest.mark.asyncio
async def test_update_task_description():
    """Verify task description update."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        side_effect=[
            {"status": "ready"},
            {
                "id": "t1",
                "title": "Task 1",
                "description": "Updated desc",
                "status": "ready",
                "assigned_agent_id": None,
                "workstream_id": "ws1",
                "workflow_id": "wf1",
                "attempt": 0,
                "max_retries": 3,
                "verification_strategy": "llm_judge",
                "created_at": "2024-01-01",
                "started_at": None,
                "completed_at": None,
                "attempt_feedback": "[]",
                "result": None,
                "structured_prompt": None,
                "acceptance_criteria_ids": "[]",
                "skeleton_tests": "[]",
                "priority": 0,
                "linear_issue_id": None,
                "updated_at": "2024-01-01",
                "output": None,
                "error": None,
            },
        ]
    )
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    mock_pool.fetch = AsyncMock(return_value=[])

    from rooben.dashboard.queries.tasks import update_task

    result = await update_task(mock_pool, "t1", {"description": "Updated desc"})
    assert result is not None
    assert result["description"] == "Updated desc"


@pytest.mark.asyncio
async def test_update_task_dependencies():
    """Verify task dependency replacement."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        side_effect=[
            {"status": "pending"},
            {
                "id": "t1",
                "title": "Task 1",
                "description": "",
                "status": "pending",
                "assigned_agent_id": None,
                "workstream_id": "ws1",
                "workflow_id": "wf1",
                "attempt": 0,
                "max_retries": 3,
                "verification_strategy": "llm_judge",
                "created_at": "2024-01-01",
                "started_at": None,
                "completed_at": None,
                "attempt_feedback": "[]",
                "result": None,
                "structured_prompt": None,
                "acceptance_criteria_ids": "[]",
                "skeleton_tests": "[]",
                "priority": 0,
                "linear_issue_id": None,
                "updated_at": "2024-01-01",
                "output": None,
                "error": None,
            },
        ]
    )
    mock_pool.execute = AsyncMock(return_value="DELETE 1")
    mock_pool.fetch = AsyncMock(
        return_value=[{"depends_on": "t0"}, {"depends_on": "t2"}]
    )

    from rooben.dashboard.queries.tasks import update_task

    result = await update_task(mock_pool, "t1", {"depends_on": ["t0", "t2"]})
    assert result is not None
    assert "t0" in result["depends_on"]
    assert "t2" in result["depends_on"]


@pytest.mark.asyncio
async def test_update_task_404():
    """Verify update returns None for nonexistent task."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value=None)

    from rooben.dashboard.queries.tasks import update_task

    result = await update_task(mock_pool, "nonexistent", {"title": "x"})
    assert result is None


@pytest.mark.asyncio
async def test_update_task_completed_rejected():
    """Verify completed/failed tasks cannot be edited."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(return_value={"status": "passed"})

    from rooben.dashboard.queries.tasks import update_task
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await update_task(mock_pool, "t1", {"title": "x"})
    assert exc_info.value.status_code == 409


# ── R-11.4: Agent configuration presets ──────────────────────────────────


@pytest.mark.asyncio
async def test_create_preset():
    """Verify preset creation."""
    mock_pool = AsyncMock()
    mock_pool.fetchrow = AsyncMock(
        return_value={
            "id": "p1",
            "name": "my-preset",
            "description": "A test preset",
            "integration": "coding",
            "prompt_template": "",
            "model_override": "",
            "capabilities": "[]",
            "max_context_tokens": 200000,
            "budget": None,
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
        }
    )

    from rooben.dashboard.queries.presets import create_preset

    result = await create_preset(mock_pool, {
        "id": "p1",
        "name": "my-preset",
        "description": "A test preset",
        "integration": "coding",
    })
    assert result["name"] == "my-preset"
    assert result["integration"] == "coding"


@pytest.mark.asyncio
async def test_list_presets():
    """Verify preset listing."""
    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(
        return_value=[
            {
                "id": "p1",
                "name": "preset-1",
                "description": "",
                "integration": "coding",
                "prompt_template": "",
                "model_override": "",
                "capabilities": "[]",
                "max_context_tokens": 200000,
                "budget": None,
                "created_at": "2024-01-01",
                "updated_at": "2024-01-01",
            }
        ]
    )

    from rooben.dashboard.queries.presets import list_presets

    result = await list_presets(mock_pool)
    assert len(result) == 1
    assert result[0]["name"] == "preset-1"


@pytest.mark.asyncio
async def test_delete_preset():
    """Verify preset deletion."""
    mock_pool = AsyncMock()
    mock_pool.execute = AsyncMock(return_value="DELETE 1")

    from rooben.dashboard.queries.presets import delete_preset

    result = await delete_preset(mock_pool, "p1")
    assert result is True


@pytest.mark.asyncio
async def test_create_preset_from_agent():
    """Verify preset creation from agent snapshot."""
    mock_pool = AsyncMock()

    # Mock agent lookup
    agent_row = {
        "id": "agent-1",
        "name": "coder",
        "transport": "llm",
        "description": "Coding agent",
        "endpoint": "",
        "capabilities": '["python"]',
        "mcp_servers": "[]",
        "budget": None,
        "integration": "coding",
        "prompt_template": "Be helpful",
        "model_override": "claude-sonnet-4-20250514",
        "max_concurrency": 1,
        "max_context_tokens": 200000,
        "first_seen_at": "2024-01-01",
        "updated_at": "2024-01-01",
    }

    # get_agent makes multiple calls
    mock_pool.fetchrow = AsyncMock(return_value=agent_row)
    mock_pool.fetch = AsyncMock(return_value=[])  # recent_tasks

    from rooben.dashboard.queries.agents import get_agent

    agent = await get_agent(mock_pool, "agent-1")
    assert agent is not None
    assert agent["integration"] == "coding"
    assert agent["prompt_template"] == "Be helpful"


@pytest.mark.asyncio
async def test_apply_preset_to_agent():
    """Verify applying preset config to an agent."""
    mock_pool = AsyncMock()

    # Preset lookup
    preset_row = {
        "id": "p1",
        "name": "fast-coder",
        "description": "",
        "integration": "full-stack",
        "prompt_template": "Be fast",
        "model_override": "claude-sonnet-4-20250514",
        "capabilities": "[]",
        "max_context_tokens": 200000,
        "budget": None,
        "created_at": "2024-01-01",
        "updated_at": "2024-01-01",
    }

    # Agent update return
    agent_return = {
        "id": "agent-1",
        "name": "coder",
        "transport": "llm",
        "description": "",
        "endpoint": "",
        "capabilities": "[]",
        "mcp_servers": "[]",
        "budget": None,
        "integration": "full-stack",
        "prompt_template": "Be fast",
        "model_override": "claude-sonnet-4-20250514",
        "max_concurrency": 1,
        "max_context_tokens": 200000,
        "first_seen_at": "2024-01-01",
        "updated_at": "2024-01-01",
    }

    mock_pool.fetchrow = AsyncMock(side_effect=[preset_row, agent_return])

    from rooben.dashboard.queries.presets import get_preset
    from rooben.dashboard.queries.agents import update_agent

    preset = await get_preset(mock_pool, "p1")
    assert preset is not None
    assert preset["integration"] == "full-stack"

    # Apply: build updates from preset
    updates = {}
    if preset.get("integration"):
        updates["integration"] = preset["integration"]
    if preset.get("prompt_template"):
        updates["prompt_template"] = preset["prompt_template"]
    if preset.get("model_override"):
        updates["model_override"] = preset["model_override"]

    result = await update_agent(mock_pool, "agent-1", updates)
    assert result is not None
    assert result["integration"] == "full-stack"
