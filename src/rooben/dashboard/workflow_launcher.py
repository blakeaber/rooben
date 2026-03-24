"""Shared workflow creation logic used by API, scheduler, and retry."""

from __future__ import annotations

import asyncio
import json as _json
import uuid
from pathlib import Path
from typing import Any

import structlog

from rooben.dashboard.deps import get_deps
from rooben.dashboard.workflow_registry import get_registry

log = structlog.get_logger()


async def launch_workflow(
    description: str,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
    integration_names: list[str] | None = None,
    schedule_id: str | None = None,
    spec_yaml: str | None = None,
    context_inputs: list[dict[str, Any]] | None = None,
    user_context: dict | None = None,
) -> str:
    """Launch a workflow in the background and return its ID immediately.

    Spec generation (which can take 10-30s) now happens inside the
    background task so the API response is instant.

    Called by: run.py (API), scheduler (cron), lifecycle.py (retry).
    """
    from rooben.dashboard.event_adapter import DashboardEventAdapter
    from rooben.dashboard.routes.events import broadcaster

    deps = get_deps()
    if not deps.pool:
        raise RuntimeError("Database not available")

    # Generate workflow ID and insert placeholder row immediately
    workflow_id = f"wf-{uuid.uuid4().hex[:8]}"

    insert_sql = """INSERT INTO workflows (id, spec_id, status, created_at, workspace_dir, input_context)
           VALUES ($1, $2, 'planning', now(), $3, $4::jsonb)
           ON CONFLICT (id) DO UPDATE SET workspace_dir = $3, input_context = $4::jsonb"""
    insert_params: list[Any] = [workflow_id, "", None, "[]"]

    if user_context and user_context.get("user_id"):
        insert_sql = """INSERT INTO workflows (id, spec_id, status, created_at, workspace_dir, input_context, user_id, org_id)
           VALUES ($1, $2, 'planning', now(), $3, $4::jsonb, $5, $6)
           ON CONFLICT (id) DO UPDATE SET workspace_dir = $3, input_context = $4::jsonb"""
        insert_params.extend([user_context["user_id"], user_context.get("org_id")])

    await deps.pool.execute(insert_sql, *insert_params)

    # Link schedule if applicable
    if schedule_id:
        await deps.pool.execute(
            """INSERT INTO schedule_executions (schedule_id, workflow_id, status, started_at)
               VALUES ($1, $2, 'running', now())""",
            schedule_id,
            workflow_id,
        )

    # Wire event adapter (broadcast-only — DB writes are via PostgresStateBackend)
    adapter = DashboardEventAdapter(pool=deps.pool, broadcaster=broadcaster)

    async def event_callback(event_type: str, payload: dict) -> None:
        await adapter.handle_event(event_type, payload)

    registry = get_registry()

    async def _run() -> None:
        try:
            # Phase 0: Generate or parse spec (this was blocking the API call)
            await event_callback("workflow.spec_generating", {"workflow_id": workflow_id})

            if spec_yaml:
                from rooben.spec.loader import load_spec_from_string
                spec = load_spec_from_string(spec_yaml)
            else:
                from rooben.refinement.oneshot import generate_spec_oneshot
                from rooben.dashboard.orchestrator_factory import _build_provider
                llm_provider = _build_provider(provider, model)
                spec = await generate_spec_oneshot(llm_provider, description)

            await event_callback("workflow.spec_ready", {"workflow_id": workflow_id})

            # Inject external integrations if requested
            if integration_names:
                from rooben.dashboard.orchestrator_factory import build_integration_registry
                from rooben.spec.models import AgentTransport

                integration_registry = build_integration_registry()
                workspace_dir = spec.workspace_dir or "."
                for agent in spec.agents:
                    if not agent.mcp_servers:
                        for integ_name in integration_names:
                            integ = integration_registry.get(integ_name)
                            if integ and integ.kind != "llm_provider":
                                servers = integ.mcp_server_factory(workspace_dir)
                                if servers:
                                    agent.transport = AgentTransport.MCP
                                    agent.mcp_servers = servers
                                    break

            # Create workspace
            workspace_id = uuid.uuid4().hex[:12]
            workspace_dir = str((Path(".rooben/workspaces") / workspace_id).resolve())
            Path(workspace_dir).mkdir(parents=True, exist_ok=True)
            spec.workspace_dir = workspace_dir

            # Process context inputs (files + URLs)
            input_context_metadata: list[dict[str, Any]] = []
            if context_inputs:
                import base64

                input_dir = Path(workspace_dir) / "input"
                input_dir.mkdir(parents=True, exist_ok=True)

                urls: list[str] = []
                for ci in context_inputs:
                    if ci.get("type") == "file" and ci.get("content_base64"):
                        fname = ci.get("filename") or f"file_{len(input_context_metadata)}"
                        data = base64.b64decode(ci["content_base64"])
                        (input_dir / fname).write_bytes(data)
                        input_context_metadata.append({
                            "type": "file",
                            "filename": fname,
                            "size_bytes": len(data),
                        })
                    elif ci.get("type") == "url" and ci.get("url"):
                        urls.append(ci["url"])
                        input_context_metadata.append({
                            "type": "url",
                            "url": ci["url"],
                        })

                if urls:
                    (input_dir / "urls.txt").write_text("\n".join(urls) + "\n")

            # Update placeholder row with resolved spec_id + workspace
            await deps.pool.execute(
                """UPDATE workflows SET spec_id = $2, workspace_dir = $3,
                       input_context = $4::jsonb
                   WHERE id = $1""",
                workflow_id, spec.id, workspace_dir,
                _json.dumps(input_context_metadata),
            )

            # Seed agents + spec metadata (moved from event adapter's
            # _handle_workflow_planned, which no longer writes to DB)
            await _seed_agents_and_spec(deps.pool, workflow_id, spec)

            # Build orchestrator with PostgresStateBackend
            from rooben.dashboard.orchestrator_factory import build_orchestrator
            orchestrator, mcp_pool = build_orchestrator(
                spec=spec,
                provider_name=provider,
                model=model,
                event_callback=event_callback,
                pg_pool=deps.pool,
            )

            # Phase 1-3: Plan → Execute → Finalize
            try:
                await orchestrator.run(spec, workflow_id=workflow_id)
            finally:
                await mcp_pool.close_all()

        except Exception as exc:
            log.error(
                "workflow_launcher.run_failed",
                workflow_id=workflow_id,
                error=str(exc),
                exc_info=True,
            )
            try:
                await deps.pool.execute(
                    """UPDATE workflows SET status = 'failed', completed_at = now()
                       WHERE id = $1 AND status != 'completed'""",
                    workflow_id,
                )
                # Pending tasks stay PENDING for retry — don't cancel them
            except Exception:
                pass
        finally:
            registry.unregister(workflow_id)
            if schedule_id:
                try:
                    await deps.pool.execute(
                        """UPDATE schedule_executions
                           SET status = (SELECT status FROM workflows WHERE id = $1),
                               completed_at = now()
                           WHERE workflow_id = $1""",
                        workflow_id,
                    )
                    await deps.pool.execute(
                        """UPDATE schedules SET last_run_at = now() WHERE id = $1""",
                        schedule_id,
                    )
                except Exception:
                    pass

    task = asyncio.create_task(_run())
    # Register with a placeholder orchestrator — the real one is created
    # inside _run() after spec generation completes.
    registry.register(workflow_id, None, task)

    return workflow_id


async def resume_workflow(workflow_id: str) -> None:
    """Resume a workflow from persisted state. Only PENDING tasks execute.

    Used by the retry-failed endpoint to re-run failed/cancelled tasks
    while keeping passed task outputs.
    """
    from rooben.dashboard.event_adapter import DashboardEventAdapter
    from rooben.dashboard.orchestrator_factory import build_orchestrator
    from rooben.dashboard.routes.events import broadcaster
    from rooben.spec.loader import load_spec_from_string

    deps = get_deps()
    if not deps.pool:
        raise RuntimeError("Database not available")

    row = await deps.pool.fetchrow(
        "SELECT spec_yaml, workspace_dir FROM workflows WHERE id = $1",
        workflow_id,
    )
    if not row or not row["spec_yaml"]:
        raise ValueError(f"Workflow {workflow_id} spec not found")

    spec = load_spec_from_string(row["spec_yaml"])
    spec.workspace_dir = row["workspace_dir"]

    adapter = DashboardEventAdapter(pool=deps.pool, broadcaster=broadcaster)

    async def event_callback(event_type: str, payload: dict) -> None:
        await adapter.handle_event(event_type, payload)

    orchestrator, mcp_pool = build_orchestrator(
        spec=spec,
        event_callback=event_callback,
        pg_pool=deps.pool,
    )

    registry = get_registry()

    async def _run() -> None:
        try:
            await orchestrator.resume(workflow_id)
        except Exception as exc:
            log.error(
                "workflow_launcher.resume_failed",
                workflow_id=workflow_id,
                error=str(exc),
                exc_info=True,
            )
            try:
                await deps.pool.execute(
                    """UPDATE workflows SET status = 'failed', completed_at = now()
                       WHERE id = $1 AND status != 'completed'""",
                    workflow_id,
                )
            except Exception:
                pass
        finally:
            await mcp_pool.close_all()
            registry.unregister(workflow_id)

    task = asyncio.create_task(_run())
    registry.register(workflow_id, orchestrator, task)


async def _seed_agents_and_spec(pool: Any, workflow_id: str, spec: Any) -> None:
    """Seed agents, workflow_agents, and spec metadata into PG.

    This was previously done by DashboardEventAdapter._handle_workflow_planned.
    Now done directly by the launcher since it's a one-time write at creation.
    """
    # Spec metadata
    spec_metadata = {
        "title": spec.title,
        "goal": spec.goal,
        "context": spec.context,
        "deliverables": [d.model_dump() for d in spec.deliverables],
        "agents": [{"id": a.id, "name": a.name, "description": a.description} for a in spec.agents],
        "constraints": [c.model_dump() for c in spec.constraints],
        "acceptance_criteria": [
            ac.model_dump() for ac in spec.success_criteria.acceptance_criteria
        ],
        "global_budget": spec.global_budget.model_dump() if spec.global_budget else None,
    }

    await pool.execute(
        """UPDATE workflows SET spec_yaml = $2, spec_metadata = $3::jsonb
           WHERE id = $1""",
        workflow_id,
        spec.model_dump_json(indent=2),
        _json.dumps(spec_metadata),
    )

    # Agents
    for agent in spec.agents:
        agent_id = agent.id
        if not agent_id:
            continue
        agent_data = agent.model_dump()
        await pool.execute(
            """INSERT INTO agents (id, name, transport, description, endpoint,
                                   capabilities, max_concurrency, max_context_tokens,
                                   budget, mcp_servers)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9::jsonb, $10::jsonb)
               ON CONFLICT (id) DO UPDATE
               SET name = $2, transport = $3, description = $4, endpoint = $5,
                   capabilities = $6::jsonb, max_concurrency = $7,
                   max_context_tokens = $8, budget = $9::jsonb,
                   mcp_servers = $10::jsonb, updated_at = now()""",
            agent_id,
            agent_data.get("name", ""),
            agent_data.get("transport", "llm"),
            agent_data.get("description", ""),
            agent_data.get("endpoint", ""),
            _json.dumps(agent_data.get("capabilities", [])),
            agent_data.get("max_concurrency", 1),
            agent_data.get("max_context_tokens", 200000),
            _json.dumps(agent_data.get("budget")) if agent_data.get("budget") else None,
            _json.dumps(agent_data.get("mcp_servers", [])),
        )
        await pool.execute(
            """INSERT INTO workflow_agents (workflow_id, agent_id)
               VALUES ($1, $2)
               ON CONFLICT DO NOTHING""",
            workflow_id, agent_id,
        )
