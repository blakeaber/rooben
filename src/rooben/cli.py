"""CLI entry point — thin wrapper over the orchestrator."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
)


@click.group()
@click.version_option(package_name="rooben")
def main() -> None:
    """Rooben — autonomous agent orchestration framework."""
    from dotenv import load_dotenv
    load_dotenv(Path(".env"))
    load_dotenv(Path(".rooben/.env"))


@main.command()
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "openai", "ollama", "bedrock"]),
    default="anthropic",
    help="LLM provider to use.",
)
def init(provider: str) -> None:
    """Set up Rooben: choose provider, configure API key, validate connectivity."""
    env_path = Path(".env")

    click.echo("Welcome to Rooben!\n")

    # Prompt for API key
    import os
    provider_config = {
        "anthropic": ("ANTHROPIC_API_KEY", "claude-sonnet-4-20250514"),
        "openai": ("OPENAI_API_KEY", "gpt-4o-mini"),
        "ollama": (None, "llama3.1"),  # No API key needed
        "bedrock": (None, "us.anthropic.claude-sonnet-4-20250514-v1:0"),  # Uses AWS creds
    }
    env_var, default_model = provider_config[provider]

    if env_var:
        key = click.prompt(f"Enter your {provider.title()} API key", hide_input=True)
        if not key.strip():
            click.echo("Error: API key cannot be empty.", err=True)
            sys.exit(1)
        os.environ[env_var] = key
    else:
        key = None
        click.echo(f"  {provider.title()} uses local/AWS credentials (no API key needed).")

    # Validate connectivity
    click.echo("Validating API connectivity...")
    try:
        llm = _build_provider(provider, default_model)
        asyncio.run(_validate_provider(llm))
        click.echo("  API key is valid.\n")
    except Exception as exc:
        click.echo(f"  API validation failed: {exc}", err=True)
        sys.exit(1)

    # Write .env file (only if provider uses an API key)
    if env_var and key:
        existing = ""
        if env_path.exists():
            existing = env_path.read_text()
        lines = [line for line in existing.splitlines() if not line.startswith(f"{env_var}=")]
        lines.append(f"{env_var}={key}")
        env_path.write_text("\n".join(lines) + "\n")
    click.echo(f"  Saved {env_var} to .env")

    # Ensure .rooben directory exists
    Path(".rooben/state").mkdir(parents=True, exist_ok=True)
    Path(".rooben/workspaces").mkdir(parents=True, exist_ok=True)
    click.echo("  Created .rooben/ directories")

    # Pre-install MCP npm packages
    click.echo("  Installing MCP tool packages...")
    from rooben.agents.integrations import ensure_mcp_packages_installed
    ensure_mcp_packages_installed()
    click.echo("  MCP packages ready")

    click.echo("\nSetup complete! Next steps:")
    click.echo("  rooben go \"Build a REST API\"        # Quick start")
    click.echo("  rooben run examples/hello_api.yaml   # Run example spec")
    click.echo("  rooben doctor                        # Check system health")


async def _validate_provider(provider) -> None:  # noqa: ANN001
    """Make a lightweight test call to validate the provider."""
    result = await provider.generate(
        system="You are a test. Respond with exactly: ok",
        prompt="ping",
        max_tokens=10,
    )
    if not result.text.strip():
        raise ValueError("Empty response from API")


@main.command()
def doctor() -> None:
    """Check system health: Python version, API keys, dependencies, state directory."""
    import importlib
    import os
    import platform

    checks_passed = 0
    checks_failed = 0

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal checks_passed, checks_failed
        icon = "PASS" if passed else "FAIL"
        msg = f"  [{icon}] {name}"
        if detail:
            msg += f" — {detail}"
        click.echo(msg)
        if passed:
            checks_passed += 1
        else:
            checks_failed += 1

    click.echo("Rooben Health Check\n")

    # Python version
    py_ver = platform.python_version()
    py_ok = sys.version_info >= (3, 11)
    check("Python version", py_ok, f"{py_ver}" + ("" if py_ok else " (need 3.11+)"))

    # API keys
    from rooben.agents.integrations import resolve_credential
    anthropic_key = resolve_credential("ANTHROPIC_API_KEY")
    openai_key = resolve_credential("OPENAI_API_KEY")
    check("Anthropic API key", bool(anthropic_key), "set" if anthropic_key else "not set")
    check("OpenAI API key (optional)", True, "set" if openai_key else "not set (optional)")

    # Core dependencies
    for dep in ["anthropic", "click", "pydantic", "structlog", "httpx"]:
        try:
            mod = importlib.import_module(dep)
            ver = getattr(mod, "__version__", "installed")
            check(f"Dependency: {dep}", True, ver)
        except ImportError:
            check(f"Dependency: {dep}", False, "not installed")

    # Optional dependencies
    for dep, extra in [("asyncpg", "postgres"), ("mcp", "mcp"), ("openai", "openai")]:
        try:
            importlib.import_module(dep)
            check(f"Optional: {dep} [{extra}]", True, "installed")
        except ImportError:
            check(f"Optional: {dep} [{extra}]", True, "not installed (optional)")

    # State directory
    state_dir = Path(".rooben/state")
    state_ok = state_dir.exists() and os.access(state_dir, os.W_OK)
    check("State directory", state_ok,
          str(state_dir) + (" (writable)" if state_ok else " (missing or not writable — run rooben init)"))

    # .env file
    env_exists = Path(".env").exists()
    check(".env file", env_exists, "found" if env_exists else "not found — run rooben init")

    # MCP npm packages
    from rooben.agents.integrations import check_mcp_packages_available
    mcp_ok = check_mcp_packages_available()
    check("MCP npm packages", mcp_ok,
          "cached" if mcp_ok else "not cached — run rooben init to pre-install")

    # API connectivity (if key present)
    if anthropic_key:
        click.echo("\n  Testing API connectivity...")
        try:
            provider = _build_provider("anthropic", "claude-sonnet-4-20250514")
            asyncio.run(_validate_provider(provider))
            check("Anthropic API connectivity", True, "responding")
        except Exception as exc:
            check("Anthropic API connectivity", False, str(exc)[:80])

    # Summary
    click.echo(f"\n  {checks_passed} passed, {checks_failed} failed")
    if checks_failed > 0:
        sys.exit(1)


@main.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option(
    "--backend",
    type=click.Choice(["filesystem"]),
    default="filesystem",
    help="State backend to use (Pro extensions may register additional backends).",
)
@click.option(
    "--state-dir",
    default=".rooben/state",
    help="Directory for filesystem state.",
)
@click.option(
    "--model",
    default="claude-sonnet-4-20250514",
    help="Default LLM model (used for all roles unless overridden).",
)
@click.option("--model-planner", default=None, help="Model for planning (default: --model).")
@click.option("--model-agent", default=None, help="Model for agent execution (default: --model).")
@click.option("--model-verifier", default=None, help="Model for verification (default: --model).")
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "openai", "ollama", "bedrock"]),
    default="anthropic",
    help="LLM provider to use.",
)
@click.option("--verbose", "-v", is_flag=True, help="Print full LLM prompts, responses, and token usage.")
def run(
    spec_path: str, backend: str, state_dir: str, model: str,
    model_planner: str | None, model_agent: str | None, model_verifier: str | None,
    provider: str, verbose: bool,
) -> None:
    """Run a specification file through the orchestrator."""
    asyncio.run(_run_async(
        spec_path, backend, state_dir, model, provider, verbose,
        model_planner=model_planner, model_agent=model_agent, model_verifier=model_verifier,
    ))


def _build_provider(provider_name: str, model: str):  # noqa: ANN201
    """Build an LLM provider by name."""
    if provider_name == "openai":
        from rooben.planning.openai_provider import OpenAIProvider
        return OpenAIProvider(model=model)
    elif provider_name == "ollama":
        from rooben.planning.ollama_provider import OllamaProvider
        return OllamaProvider(model=model)
    elif provider_name == "bedrock":
        from rooben.planning.bedrock_provider import BedrockProvider
        return BedrockProvider(model_id=model)
    else:
        from rooben.planning.provider import AnthropicProvider
        return AnthropicProvider(model=model)


async def _run_async(
    spec_path: str, backend: str, state_dir: str, model: str, provider_name: str,
    verbose: bool = False,
    model_planner: str | None = None, model_agent: str | None = None, model_verifier: str | None = None,
) -> None:
    from rooben.agents.registry import AgentRegistry
    from rooben.orchestrator import Orchestrator
    from rooben.planning.llm_planner import LLMPlanner
    from rooben.spec.loader import load_spec
    from rooben.verification.llm_judge import LLMJudgeVerifier

    log = structlog.get_logger()

    # Load spec
    spec = load_spec(spec_path)
    log.info("cli.spec_loaded", spec_id=spec.id, title=spec.title)

    # Build per-role providers (R-3.4: Multi-Model Routing)
    planner_provider = _build_provider(provider_name, model_planner or model)
    agent_provider = _build_provider(provider_name, model_agent or model)
    verifier_provider = _build_provider(provider_name, model_verifier or model)
    if verbose:
        from rooben.planning.provider import VerboseProvider
        planner_provider = VerboseProvider(planner_provider)
        agent_provider = VerboseProvider(agent_provider)
        verifier_provider = VerboseProvider(verifier_provider)

    # Build planner
    planner = LLMPlanner(provider=planner_provider)

    # Build MCP connection pool (R-3.6)
    from rooben.agents.mcp_pool import MCPConnectionPool
    mcp_pool = MCPConnectionPool()

    # Resolve system capabilities + external integrations for agents
    from rooben.agents.integrations import IntegrationRegistry, load_user_integrations
    from rooben.spec.models import AgentTransport

    integration_registry = IntegrationRegistry()
    load_user_integrations(integration_registry)

    workspace_dir = str(Path(spec_path).parent)
    for agent in spec.agents:
        if not agent.mcp_servers:
            _name, servers = integration_registry.resolve_for_agent(agent, workspace_dir)
            if servers:
                agent.transport = AgentTransport.MCP
                agent.mcp_servers = servers

    # Build agent registry
    registry = AgentRegistry(llm_provider=agent_provider, connection_pool=mcp_pool)
    registry.register_from_specs(spec.agents)

    # Build state backend
    state_backend = _build_backend(backend, state_dir)

    # Build verifier
    verifier = LLMJudgeVerifier(provider=verifier_provider)

    # Build and run orchestrator
    orchestrator = Orchestrator(
        planner=planner,
        agent_registry=registry,
        backend=state_backend,
        verifier=verifier,
        budget=spec.global_budget,
    )

    from rooben.security.budget import BudgetExceeded

    try:
        state = await orchestrator.run(spec)
    except BudgetExceeded as exc:
        click.echo(f"\nBudget exceeded: {exc}", err=True)
        # Still try to print partial results
        state = orchestrator._state
        if not state:
            sys.exit(1)
    finally:
        await mcp_pool.close_all()

    # Print summary
    for wf in state.workflows.values():
        click.echo(f"\nWorkflow {wf.id}: {wf.status.value}")
        click.echo(f"  Tasks: {wf.completed_tasks} passed, {wf.failed_tasks} failed, {wf.total_tasks} total")

    # Surface workflow report
    if orchestrator.last_report:
        click.echo(f"\n{orchestrator._reporter.format_report(orchestrator.last_report)}", err=True)

    # Surface diagnostic report if present
    if orchestrator.last_diagnostic:
        from rooben.observability.diagnostics import DiagnosticAnalyzer
        click.echo(DiagnosticAnalyzer().format_report(orchestrator.last_diagnostic), err=True)



def _build_backend(backend: str, state_dir: str):  # noqa: ANN201
    if backend == "filesystem":
        from rooben.state.filesystem import FilesystemBackend
        return FilesystemBackend(base_dir=state_dir)
    raise click.BadParameter(f"Unknown backend: {backend}")


@main.command()
@click.argument("workflow_id")
@click.option(
    "--backend",
    type=click.Choice(["filesystem"]),
    default="filesystem",
    help="State backend to use (Pro extensions may register additional backends).",
)
@click.option("--state-dir", default=".rooben/state")
@click.option(
    "--model",
    default="claude-sonnet-4-20250514",
    help="LLM model to use.",
)
@click.option(
    "--spec-path",
    type=click.Path(exists=True),
    required=True,
    help="Original spec file (needed to rebuild agent registry).",
)
def resume(
    workflow_id: str, backend: str, state_dir: str, model: str, spec_path: str
) -> None:
    """Resume an incomplete workflow from saved state."""
    asyncio.run(_resume_async(workflow_id, backend, state_dir, model, spec_path))


async def _resume_async(
    workflow_id: str, backend: str, state_dir: str, model: str, spec_path: str
) -> None:
    from rooben.agents.registry import AgentRegistry
    from rooben.orchestrator import Orchestrator
    from rooben.planning.llm_planner import LLMPlanner
    from rooben.planning.provider import AnthropicProvider
    from rooben.spec.loader import load_spec
    from rooben.verification.llm_judge import LLMJudgeVerifier

    log = structlog.get_logger()

    spec = load_spec(spec_path)
    provider = AnthropicProvider(model=model)
    planner = LLMPlanner(provider=provider)
    registry = AgentRegistry(llm_provider=provider)
    registry.register_from_specs(spec.agents)
    state_backend = _build_backend(backend, state_dir)
    verifier = LLMJudgeVerifier(provider=provider)

    orchestrator = Orchestrator(
        planner=planner,
        agent_registry=registry,
        backend=state_backend,
        verifier=verifier,
        budget=spec.global_budget,
    )

    from rooben.security.budget import BudgetExceeded

    try:
        state = await orchestrator.resume(workflow_id)
    except BudgetExceeded as exc:
        click.echo(f"\nBudget exceeded: {exc}", err=True)
        state = orchestrator._state
        if not state:
            sys.exit(1)

    for wf in state.workflows.values():
        click.echo(f"\nWorkflow {wf.id}: {wf.status.value}")
        click.echo(f"  Tasks: {wf.completed_tasks} passed, {wf.failed_tasks} failed, {wf.total_tasks} total")

    log.info("cli.resume_complete", workflow_id=workflow_id)


@main.command()
@click.argument("workflow_id")
def cancel(workflow_id: str) -> None:
    """Cancel a running workflow via the dashboard API."""
    asyncio.run(_cancel_async(workflow_id))


async def _cancel_async(workflow_id: str) -> None:
    from rooben.cli_api import APIClient
    client = APIClient()
    try:
        result = await client.post(f"/api/workflows/{workflow_id}/cancel")
        click.echo(f"Workflow {workflow_id}: {result.get('status', 'cancelled')}")
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@main.command()
@click.argument("workflow_id")
@click.option("--state-dir", default=".rooben/state")
@click.option("--api", is_flag=True, help="Query dashboard API instead of filesystem.")
def status(workflow_id: str, state_dir: str, api: bool) -> None:
    """Show the status of a workflow."""
    if api:
        asyncio.run(_status_api_async(workflow_id))
    else:
        asyncio.run(_status_async(workflow_id, state_dir))


async def _status_async(workflow_id: str, state_dir: str) -> None:
    from rooben.state.filesystem import FilesystemBackend

    backend = FilesystemBackend(base_dir=state_dir)
    await backend.initialize()
    state = await backend.load_state(workflow_id)

    if not state:
        click.echo(f"Workflow {workflow_id} not found.")
        sys.exit(1)

    for wf in state.workflows.values():
        click.echo(f"Workflow: {wf.id} ({wf.status.value})")
        click.echo(f"  Total tasks: {wf.total_tasks}")
        click.echo(f"  Completed: {wf.completed_tasks}")
        click.echo(f"  Failed: {wf.failed_tasks}")

    click.echo("\nWorkstreams:")
    for ws in state.workstreams.values():
        click.echo(f"  {ws.name} ({ws.status.value})")

    click.echo("\nTasks:")
    for task in state.tasks.values():
        agent = task.assigned_agent_id or "unassigned"
        click.echo(f"  [{task.status.value:12s}] {task.title} (agent: {agent})")


@main.command()
@click.option("--output", "-o", default="spec.yaml", help="Output path for generated spec YAML.")
@click.option("--model", default="claude-sonnet-4-20250514", help="LLM model to use.")
@click.option("--max-turns", default=20, type=int, help="Max conversation turns.")
def refine(output: str, model: str, max_turns: int) -> None:
    """Interactively refine a project idea into a specification."""
    asyncio.run(_refine_async(output, model, max_turns))


def _present_questions(questions) -> str:  # noqa: ANN001
    """Present structured questions with numbered choices, return user's answer."""
    from rooben.refinement.state import StructuredQuestion

    for q in questions:
        if isinstance(q, StructuredQuestion) and q.choices:
            click.echo(f"\n{q.text}")
            for i, choice in enumerate(q.choices, 1):
                click.echo(f"  [{i}] {choice}")
            if q.allow_freeform:
                click.echo(f"  [{len(q.choices) + 1}] Other (type your answer)")
        elif isinstance(q, StructuredQuestion):
            click.echo(f"\n{q.text}")
        else:
            click.echo(f"\n{q}")

    raw = click.prompt("\nYour answer")

    # Resolve numbered selection to the choice text
    if questions and isinstance(questions[0], StructuredQuestion) and questions[0].choices:
        try:
            idx = int(raw.strip())
            choices = questions[0].choices
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
            # If they picked the "Other" number, prompt for freeform
            if idx == len(choices) + 1:
                return click.prompt("  Please specify")
        except ValueError:
            pass  # Not a number — treat as free-form

    return raw


async def _refine_async(output: str, model: str, max_turns: int) -> None:
    from rooben.planning.provider import AnthropicProvider
    from rooben.refinement.engine import RefinementEngine
    from rooben.refinement.state import ConversationState

    provider = AnthropicProvider(model=model)
    engine = RefinementEngine(provider=provider, max_turns=max_turns)

    click.echo("Welcome to Rooben Refinement!")
    click.echo("Describe your project idea and I'll help you turn it into a specification.\n")

    initial = click.prompt("What would you like to build?")
    questions = await engine.start(initial)

    while True:
        answer = _present_questions(questions)
        result = await engine.process_answer(answer)

        if isinstance(result, ConversationState):
            # Entered review phase
            click.echo(f"\nCompleteness: {result.completeness:.0%}")
            click.echo("\nGenerating draft specification...\n")
            yaml_str = await engine.get_draft_yaml()
            click.echo(yaml_str)

            choice = click.prompt(
                "\n[a]ccept / [c]ontinue refining / [q]uit",
                type=click.Choice(["a", "c", "q"]),
            )
            if choice == "a":
                spec = await engine.accept()
                from rooben.refinement.spec_builder import SpecBuilder
                builder = SpecBuilder()
                yaml_out = builder.to_yaml(spec)
                with open(output, "w") as f:
                    f.write(yaml_out)
                click.echo(f"\nSpecification saved to {output}")
                return
            elif choice == "c":
                questions = await engine.continue_refining()
            else:
                click.echo("Exiting without saving.")
                return
        else:
            questions = result



@main.command()
@click.option("--host", default="127.0.0.1", help="API server host.")
@click.option("--port", default=8420, type=int, help="API server port.")
@click.option("--dev", is_flag=True, help="Run Next.js in dev mode alongside API.")
def dashboard(host: str, port: int, dev: bool) -> None:
    """Launch the Rooben dashboard."""
    from rooben.dashboard.server import run_dashboard
    run_dashboard(host=host, port=port, dev=dev)


@main.command()
def demo() -> None:
    """Run a full feature demo with mock providers (no API key needed)."""
    click.echo("Running Rooben feature demo (no API key required)...\n")
    from rooben._demo_orchestration import main as demo_main
    asyncio.run(demo_main())


@main.command()
@click.argument("description")
@click.option(
    "--backend",
    type=click.Choice(["filesystem"]),
    default="filesystem",
    help="State backend to use (Pro extensions may register additional backends).",
)
@click.option("--state-dir", default=".rooben/state", help="Directory for state.")
@click.option("--model", default="claude-sonnet-4-20250514", help="Default LLM model.")
@click.option("--model-planner", default=None, help="Model for planning (default: --model).")
@click.option("--model-agent", default=None, help="Model for agent execution (default: --model).")
@click.option("--model-verifier", default=None, help="Model for verification (default: --model).")
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "openai", "ollama", "bedrock"]),
    default="anthropic",
    help="LLM provider to use.",
)
@click.option("--save-spec", default=None, help="Save generated spec YAML to this path.")
@click.option("--dry-run", is_flag=True, help="Generate spec only, don't run.")
@click.option("--preview", is_flag=True, help="Preview spec and validation, then prompt before running.")
@click.option("--verbose", "-v", is_flag=True, help="Print full LLM prompts, responses, and token usage.")
@click.option("--refine", is_flag=True, help="Run 2-3 interactive refinement turns before execution.")
def go(
    description: str,
    backend: str,
    state_dir: str,
    model: str,
    model_planner: str | None,
    model_agent: str | None,
    model_verifier: str | None,
    provider: str,
    save_spec: str | None,
    dry_run: bool,
    preview: bool,
    verbose: bool,
    refine: bool,
) -> None:
    """Generate a spec from natural language and run it.

    Example: rooben go "Build a REST API that serves weather data"
    """
    asyncio.run(_go_async(
        description, backend, state_dir, model, provider, save_spec, dry_run, preview, verbose,
        model_planner=model_planner, model_agent=model_agent, model_verifier=model_verifier,
        refine=refine,
    ))


async def _go_async(
    description: str,
    backend: str,
    state_dir: str,
    model: str,
    provider_name: str,
    save_spec_path: str | None,
    dry_run: bool,
    preview: bool,
    verbose: bool = False,
    model_planner: str | None = None,
    model_agent: str | None = None,
    model_verifier: str | None = None,
    refine: bool = False,
) -> None:
    import uuid as _uuid

    from rooben.refinement.oneshot import generate_spec_oneshot
    from rooben.refinement.spec_builder import SpecBuilder
    from rooben.spec.validator import SpecValidator

    _log = structlog.get_logger()

    # Build provider for spec generation (uses planner model)
    llm_provider = _build_provider(provider_name, model_planner or model)
    if verbose:
        from rooben.planning.provider import VerboseProvider
        llm_provider = VerboseProvider(llm_provider)

    # Create isolated workspace for generated code
    workspace_id = _uuid.uuid4().hex[:12]
    workspace_dir = str((Path(".rooben/workspaces") / workspace_id).resolve())
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)
    click.echo(f"Workspace: {workspace_dir}")

    # Check MCP packages are available (installed during `rooben init`)
    from rooben.agents.integrations import check_mcp_packages_available, ensure_mcp_packages_installed  # noqa: E501
    if not check_mcp_packages_available():
        click.echo("Warning: MCP npm packages not cached. Installing now (run `rooben init` to pre-install)...", err=True)
        ensure_mcp_packages_installed()

    click.echo(f"Generating spec from: \"{description}\"")
    spec = await generate_spec_oneshot(llm_provider, description, workspace_dir=workspace_dir)
    # Resolve system capabilities + external integrations for agents
    from rooben.agents.integrations import IntegrationRegistry, load_user_integrations
    from rooben.spec.models import AgentTransport

    integration_registry = IntegrationRegistry()
    load_user_integrations(integration_registry)

    for agent in spec.agents:
        if not agent.mcp_servers:
            _name, servers = integration_registry.resolve_for_agent(agent, workspace_dir)
            if servers:
                agent.transport = AgentTransport.MCP
                agent.mcp_servers = servers

    click.echo(f"  Title: {spec.title}")
    click.echo(f"  Deliverables: {len(spec.deliverables)}")
    click.echo(f"  Agents: {len(spec.agents)}")
    click.echo(f"  Acceptance criteria: {len(spec.success_criteria.acceptance_criteria)}")
    click.echo(f"  Workflow hints: {len(spec.workflow_hints)}")

    # Interactive refinement (R-3.7: go --refine)
    if refine:
        from rooben.refinement.engine import RefinementEngine
        from rooben.refinement.state import ConversationState

        click.echo("\nStarting interactive refinement (2-3 turns)...")
        engine = RefinementEngine(provider=llm_provider, max_turns=3)

        # Seed the engine with the generated spec context
        spec_summary = (
            f"{description}. "
            f"Deliverables: {', '.join(d.name for d in spec.deliverables)}. "
            f"Agents: {', '.join(a.name for a in spec.agents)}."
        )
        questions = await engine.start(spec_summary)

        for turn in range(3):
            answer = _present_questions(questions)
            result = await engine.process_answer(answer)

            if isinstance(result, ConversationState):
                # Engine reached review — regenerate spec with gathered info
                click.echo("\nRegenerating spec with your refinements...")
                refined_spec = await engine.accept()
                # Merge workspace_dir from original spec
                refined_spec.workspace_dir = spec.workspace_dir
                spec = refined_spec
                click.echo(f"  Title: {spec.title}")
                click.echo(f"  Deliverables: {len(spec.deliverables)}")
                click.echo(f"  Agents: {len(spec.agents)}")
                break
            else:
                questions = result
        else:
            # Max turns reached without review — regenerate from gathered info
            click.echo("\nRegenerating spec with your refinements...")
            refined_spec = await engine.accept()
            refined_spec.workspace_dir = spec.workspace_dir
            spec = refined_spec

    # Validate the spec
    validator = SpecValidator()
    validation = validator.validate(spec)
    if not validation.is_valid:
        click.echo("\nValidation FAILED:")
        click.echo(validation.summary())
        sys.exit(1)
    elif validation.warnings:
        click.echo("\nValidation passed with warnings:")
        click.echo(validation.summary())
    else:
        click.echo("\n  Validation: passed")

    # Save spec if requested
    if save_spec_path:
        builder = SpecBuilder()
        yaml_out = builder.to_yaml(spec)
        with open(save_spec_path, "w") as f:
            f.write(yaml_out)
        click.echo(f"  Spec saved to: {save_spec_path}")

    if dry_run:
        click.echo("\nDry run — spec generated but not executed.")
        builder = SpecBuilder()
        click.echo("\n" + builder.to_yaml(spec))
        return

    if preview:
        click.echo("\nSpec preview:")
        builder = SpecBuilder()
        click.echo(builder.to_yaml(spec))

        choice = click.prompt(
            "\n[r]un / [s]ave / [q]uit",
            type=click.Choice(["r", "s", "q"]),
        )
        if choice == "s":
            out_path = save_spec_path or "spec.yaml"
            yaml_out = builder.to_yaml(spec)
            with open(out_path, "w") as f:
                f.write(yaml_out)
            click.echo(f"Spec saved to: {out_path}")
            return
        elif choice == "q":
            click.echo("Aborted.")
            return
        # choice == "r" falls through to execution

    # Run the spec
    click.echo("\nExecuting spec...")
    from rooben.agents.registry import AgentRegistry
    from rooben.orchestrator import Orchestrator
    from rooben.planning.llm_planner import LLMPlanner
    from rooben.verification.llm_judge import LLMJudgeVerifier

    # Build per-role providers (R-3.4: Multi-Model Routing)
    planner_provider = llm_provider  # Already built with planner model
    agent_provider = _build_provider(provider_name, model_agent or model)
    verifier_provider = _build_provider(provider_name, model_verifier or model)
    if verbose:
        from rooben.planning.provider import VerboseProvider as VP
        agent_provider = VP(agent_provider)
        verifier_provider = VP(verifier_provider)

    # Build MCP connection pool (R-3.6)
    from rooben.agents.mcp_pool import MCPConnectionPool
    mcp_pool = MCPConnectionPool()

    planner = LLMPlanner(provider=planner_provider)
    registry = AgentRegistry(llm_provider=agent_provider, connection_pool=mcp_pool)
    registry.register_from_specs(spec.agents)
    state_backend = _build_backend(backend, state_dir)
    verifier = LLMJudgeVerifier(provider=verifier_provider)

    orchestrator = Orchestrator(
        planner=planner,
        agent_registry=registry,
        backend=state_backend,
        verifier=verifier,
        budget=spec.global_budget,
    )

    from rooben.security.budget import BudgetExceeded

    try:
        state = await orchestrator.run(spec)
    except BudgetExceeded as exc:
        click.echo(f"\nBudget exceeded: {exc}", err=True)
        state = orchestrator._state
        if not state:
            sys.exit(1)
    finally:
        await mcp_pool.close_all()

    # Print summary
    for wf in state.workflows.values():
        click.echo(f"\nWorkflow {wf.id}: {wf.status.value}")
        click.echo(f"  Tasks: {wf.completed_tasks} passed, {wf.failed_tasks} failed, {wf.total_tasks} total")

    # Surface workflow report
    if orchestrator.last_report:
        click.echo(f"\n{orchestrator._reporter.format_report(orchestrator.last_report)}", err=True)

    # Surface diagnostic report if present
    if orchestrator.last_diagnostic:
        from rooben.observability.diagnostics import DiagnosticAnalyzer
        click.echo(DiagnosticAnalyzer().format_report(orchestrator.last_diagnostic), err=True)

    click.echo("\nView results in the dashboard:")
    click.echo("  rooben dashboard --dev")


@main.command()
@click.argument("spec_path", type=click.Path(exists=True))
def validate(spec_path: str) -> None:
    """Validate a specification file without running it."""
    from rooben.spec.loader import load_spec
    from rooben.spec.validator import SpecValidator

    try:
        spec = load_spec(spec_path)
        click.echo(f"Specification: {spec.title}")
        click.echo(f"  ID: {spec.id}")
        click.echo(f"  Deliverables: {len(spec.deliverables)}")
        click.echo(f"  Agents: {len(spec.agents)}")
        click.echo(f"  Acceptance criteria: {len(spec.success_criteria.acceptance_criteria)}")
        click.echo(f"  Constraints: {len(spec.constraints)}")

        validator = SpecValidator()
        result = validator.validate(spec)
        click.echo(f"\nValidation: {'PASSED' if result.is_valid else 'FAILED'}")
        click.echo(result.summary())
        if not result.is_valid:
            sys.exit(1)
    except Exception as exc:
        click.echo(f"Invalid specification: {exc}", err=True)
        sys.exit(1)


@main.group()
def billing() -> None:
    """Billing and cost tracking commands."""



@billing.command()
@click.argument("provider_name")
@click.argument("model_name")
@click.option("--input-tokens", default=1000, help="Input tokens to price.")
@click.option("--output-tokens", default=1000, help="Output tokens to price.")
def estimate(provider_name: str, model_name: str, input_tokens: int, output_tokens: int) -> None:
    """Estimate cost for a given provider/model and token count."""
    from rooben.billing.costs import CostRegistry
    from rooben.domain import TokenUsage

    registry = CostRegistry()
    usage = TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)

    try:
        cost = registry.calculate_cost(provider_name, model_name, usage)
        click.echo(f"Provider: {provider_name}")
        click.echo(f"Model: {model_name}")
        click.echo(f"Input tokens: {input_tokens:,}")
        click.echo(f"Output tokens: {output_tokens:,}")
        click.echo(f"Estimated cost: ${cost}")
    except KeyError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@main.group(name="integrations")
def integrations() -> None:
    """Integration registry commands."""



@integrations.command("list")
def integrations_list() -> None:
    """List all available integrations with cost tiers and availability."""
    from rooben.agents.integrations import IntegrationRegistry, load_user_integrations

    registry = IntegrationRegistry()
    load_user_integrations(registry)

    cost_symbols = {0: "$   ", 1: "$   ", 2: "$$  ", 3: "$$$"}

    click.echo("Available Integrations:\n")
    for tk in registry.list_all():
        avail = registry.is_available(tk)
        missing = registry._missing_env(tk)
        avail_str = "yes" if avail else f"no  (missing: {', '.join(missing)})"
        cost_str = cost_symbols.get(tk.cost_tier, "$$  ")
        click.echo(f"  {tk.name:20s} {tk.description:45s} Cost: {cost_str} Available: {avail_str}")


@integrations.command()
@click.argument("name")
def info(name: str) -> None:
    """Show integration details including servers and required env vars."""
    from rooben.agents.integrations import IntegrationRegistry, load_user_integrations

    registry = IntegrationRegistry()
    load_user_integrations(registry)

    tk = registry.get(name)
    if not tk:
        available = [t.name for t in registry.list_all()]
        click.echo(f"Integration '{name}' not found. Available: {', '.join(available)}", err=True)
        sys.exit(1)

    click.echo(f"Integration: {tk.name}")
    click.echo(f"  Description: {tk.description}")
    click.echo(f"  Cost tier: {tk.cost_tier}")
    click.echo(f"  Domain tags: {', '.join(tk.domain_tags) if tk.domain_tags else '(none — catch-all)'}")
    click.echo(f"  Required env: {', '.join(tk.required_env) if tk.required_env else '(none)'}")
    click.echo(f"  Available: {'yes' if registry.is_available(tk) else 'no'}")

    # Show server configs for a sample workspace
    servers = tk.mcp_server_factory("/tmp/sample-workspace")
    if servers:
        click.echo(f"\n  MCP Servers ({len(servers)}):")
        for s in servers:
            click.echo(f"    - {s.name} ({s.transport_type.value})")
            if s.command:
                click.echo(f"      command: {s.command} {' '.join(s.args)}")
            if s.url:
                click.echo(f"      url: {s.url}")
    else:
        click.echo("\n  MCP Servers: (none — pure LLM reasoning)")


@main.group()
def extensions() -> None:
    """Manage Rooben extensions (integrations, templates, agents)."""
    pass


@extensions.command("list")
@click.option("--type", "ext_type", type=click.Choice(["integration", "template", "agent"]), default=None, help="Filter by extension type.")
def extensions_list(ext_type: str | None) -> None:
    """List available and installed extensions."""
    from rooben.extensions.loader import load_all_extensions
    from rooben.extensions.installer import is_installed

    manifests = load_all_extensions()
    if ext_type:
        manifests = [m for m in manifests if m.type.value == ext_type]

    if not manifests:
        click.echo("No extensions found.")
        return

    click.echo(f"\n  Available Extensions ({len(manifests)})\n")
    for m in sorted(manifests, key=lambda x: (x.type.value, x.name)):
        installed_marker = " [installed]" if is_installed(m.name) else ""
        click.echo(f"  {m.type.value:12s}  {m.name:30s}  {m.description[:50]}{installed_marker}")
    click.echo()


@extensions.command("install")
@click.argument("name")
def extensions_install(name: str) -> None:
    """Install an extension by name."""
    from rooben.extensions.installer import install_extension

    try:
        path = install_extension(name)
        click.echo(f"Installed extension '{name}' to {path}")
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)
    except FileExistsError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


@extensions.command("uninstall")
@click.argument("name")
def extensions_uninstall(name: str) -> None:
    """Uninstall an extension by name."""
    from rooben.extensions.installer import uninstall_extension

    try:
        uninstall_extension(name)
        click.echo(f"Uninstalled extension '{name}'")
    except FileNotFoundError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)


async def _status_api_async(workflow_id: str) -> None:
    from rooben.cli_api import APIClient
    client = APIClient()
    try:
        result = await client.get(f"/api/workflows/{workflow_id}/status")
        click.echo(f"Workflow: {workflow_id} ({result.get('status', 'unknown')})")
        progress = result.get("progress", {})
        click.echo(f"  Completed: {progress.get('completed', 0)}")
        click.echo(f"  Failed: {progress.get('failed', 0)}")
        click.echo(f"  Total: {progress.get('total', 0)}")
        click.echo(f"  Live: {result.get('is_live', False)}")
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)



if __name__ == "__main__":
    main()
