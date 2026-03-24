# Custom Agents Developer Guide

## Overview

Agents are the execution units in Rooben. The orchestrator decomposes a specification into tasks and dispatches each task to an agent. Every agent implements the `AgentProtocol` interface, which defines three methods:

```python
from rooben.agents.protocol import AgentProtocol
from rooben.domain import Task, TaskResult

class AgentProtocol(Protocol):
    @property
    def agent_id(self) -> str: ...

    async def execute(self, task: Task) -> TaskResult: ...

    async def health_check(self) -> bool: ...
```

- **`agent_id`** -- A unique string identifier for this agent instance.
- **`execute(task)`** -- Receives a `Task` (with a description, acceptance criteria, and optional skeleton tests), performs work, and returns a `TaskResult` containing output text, file artifacts, generated tests, and timing metadata.
- **`health_check()`** -- Returns `True` if the agent is available and ready to accept tasks.

The orchestrator never calls agent implementations directly. It resolves agents through the `AgentRegistry`, which also enforces per-agent concurrency limits via asyncio semaphores.

---

## Transport Options

`AgentTransport` (defined in `rooben.spec.models`) determines how a task reaches the agent. There are four transports:

| Transport | Enum value | When to use | `endpoint` field |
|-----------|-----------|-------------|-----------------|
| **LLM** | `llm` | General-purpose agent backed by a language model. No external tools. | Leave empty |
| **MCP** | `mcp` | LLM-backed agent with access to external tools via MCP servers (filesystem, shell, APIs). | Leave empty; configure `mcp_servers` instead |
| **HTTP** | `http` | Delegate to a remote REST service. | Base URL, e.g. `https://agent.example.com` |
| **Subprocess** | `subprocess` | Run a Python function in an isolated child process. Good for deterministic, non-LLM tasks. | Dotted Python path, e.g. `mypackage.agents.lint_checker` |

### How each transport works

**LLM** -- Internally creates an `MCPAgent` with no MCP server configs, so it operates as a pure LLM agent. Requires an `LLMProvider` in the registry.

**MCP** -- Creates an `MCPAgent` that connects to one or more MCP servers (via stdio or SSE). The LLM orchestrates tool calls in an agentic loop: read files, run shell commands, call APIs, then return a structured `final_result`. This is the most capable transport.

**HTTP** -- Creates an `HTTPAgent` that POSTs the task to a remote endpoint. The agent sends the task as JSON and parses the response into a `TaskResult`.

**Subprocess** -- Creates a `SubprocessAgent` that spawns `python -c <runner>`, pipes the task as JSON to stdin, and reads a JSON result from stdout. The callable receives a dict and must return a dict with `output`, `artifacts`, and optionally `error`.

---

## Writing a Custom Agent

To create a custom agent, implement the `AgentProtocol` interface:

```python
import time
from rooben.domain import Task, TaskResult

class MyCustomAgent:
    """A custom agent that processes tasks."""

    def __init__(self, agent_id: str, some_config: str):
        self._agent_id = agent_id
        self._config = some_config

    @property
    def agent_id(self) -> str:
        return self._agent_id

    async def execute(self, task: Task) -> TaskResult:
        start = time.monotonic()

        try:
            # 1. Read the task
            description = task.description
            criteria = task.acceptance_criteria

            # 2. Do your work
            output = f"Processed: {description}"
            artifacts = {"result.txt": "file contents here"}

            # 3. Return a TaskResult
            return TaskResult(
                output=output,
                artifacts=artifacts,
                wall_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return TaskResult(
                error=str(exc),
                wall_seconds=time.monotonic() - start,
            )

    async def health_check(self) -> bool:
        return True
```

### TaskResult fields

- `output` (str) -- Summary of what the agent produced.
- `artifacts` (dict[str, str]) -- Map of filename to file content.
- `generated_tests` (list) -- Tests the agent created, each with `filename`, `content`, `test_type`, and `framework`.
- `error` (str | None) -- Set on failure; the orchestrator treats this as a failed task.
- `wall_seconds` (float) -- Elapsed wall-clock time.

### Subprocess callable pattern

For subprocess agents, you write a plain function (not a class):

```python
# mypackage/agents/lint_checker.py

def run(task: dict) -> dict:
    """Called by SubprocessAgent in a child process."""
    description = task["description"]

    # Do work...
    issues = check_lint(task.get("artifacts", {}))

    return {
        "output": f"Found {len(issues)} lint issues",
        "artifacts": {"lint-report.json": json.dumps(issues)},
    }
```

The `endpoint` in the spec would be `mypackage.agents.lint_checker.run`.

---

## Registering via Spec

Agents are declared in the `agents` section of a Rooben specification YAML file. The `AgentRegistry.register_from_specs()` method reads these and builds the corresponding agent instances.

### Minimal LLM agent

```yaml
agents:
  - id: writer
    name: Content Writer
    transport: llm
    description: "Writes documentation and prose content"
    capabilities: [writing, documentation]
    max_concurrency: 2
```

### MCP agent with tools

```yaml
agents:
  - id: backend-dev
    name: Backend Developer
    transport: mcp
    description: "Builds Python backend services with file and shell access"
    capabilities: [python, api, testing]
    max_concurrency: 1
    max_turns: 40
    mcp_servers:
      - name: filesystem
        transport_type: stdio
        command: npx
        args: ["-y", "@anthropic/mcp-filesystem"]
      - name: shell
        transport_type: stdio
        command: npx
        args: ["-y", "@anthropic/mcp-shell"]
    budget:
      max_tokens: 32768
      max_wall_seconds: 600
      max_retries_per_task: 2
```

### HTTP agent

```yaml
agents:
  - id: image-gen
    name: Image Generator
    transport: http
    description: "Generates images via a remote API"
    endpoint: "https://image-agent.example.com"
    capabilities: [image-generation, design]
    max_concurrency: 3
    budget:
      max_wall_seconds: 120
```

### Subprocess agent

```yaml
agents:
  - id: linter
    name: Code Linter
    transport: subprocess
    description: "Runs static analysis on Python code"
    endpoint: "mypackage.agents.lint_checker.run"
    capabilities: [python, linting]
    max_concurrency: 4
    budget:
      max_wall_seconds: 60
```

### AgentSpec fields reference

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | str | required | Unique agent identifier |
| `name` | str | required | Human-readable name |
| `transport` | `llm` \| `mcp` \| `http` \| `subprocess` | required | How tasks reach the agent |
| `description` | str | required | What this agent is good at (used by the planner) |
| `endpoint` | str | `""` | URL (http) or dotted path (subprocess) |
| `capabilities` | list[str] | `[]` | Tags for planner matching |
| `max_concurrency` | int | `1` | Max parallel tasks |
| `max_turns` | int | `40` | Max agentic loop iterations (LLM/MCP) |
| `max_context_tokens` | int | `200000` | Context window budget |
| `budget` | AgentBudget | `None` | Resource limits (see below) |
| `mcp_servers` | list[MCPServerConfig] | `[]` | MCP tool servers (MCP transport) |
| `system_capabilities` | SystemCapabilities | `None` | Declarative shell/memory/fetch access |

---

## Registering as an Extension

Extensions let you package an agent as a pip-installable Python package with a `rooben-extension.yaml` manifest. This is the recommended approach for reusable agents.

### Directory structure

```
rooben-ext-my-agent/
  rooben-extension.yaml
  pyproject.toml          # or setup.py
  src/
    my_agent/
      __init__.py
```

### The manifest file

Create `rooben-extension.yaml` in the package root:

```yaml
schema_version: 1
name: my-custom-agent
type: agent
version: 1.0.0
author: your-name
license: MIT
description: "A short description of what this agent does"
tags:
  - my-domain
  - specialty
domain_tags:
  - software
category: builder
use_cases:
  - "Use case 1"
  - "Use case 2"
min_rooben_version: 0.1.0

# Agent-specific fields
transport: llm
capabilities:
  - python
  - testing
system_capabilities:
  shell:
    enabled: true
  filesystem:
    enabled: true
    mode: readwrite
max_concurrency: 2
max_turns: 25
max_context_tokens: 200000
prompt_template: |
  You are a specialist in X. Your approach should be:
  - Thorough and methodical
  - Follow best practices for Y
  - Produce well-tested output
is_default: false
```

### Manifest fields for agents

Beyond the shared fields (`schema_version`, `name`, `type`, `version`, etc.), agent extensions use:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `transport` | str | `"llm"` | Transport type |
| `capabilities` | list[str] | `[]` | Agent capability tags |
| `system_capabilities` | dict | `None` | Shell, memory, fetch access |
| `integration` | str | `""` | External integration name |
| `model_override` | str | `""` | Override the default LLM model |
| `max_concurrency` | int | `2` | Max parallel tasks |
| `max_turns` | int | `25` | Max agentic loop turns |
| `max_context_tokens` | int | `200000` | Context window size |
| `prompt_template` | str | `""` | Custom system prompt for this agent |
| `is_default` | bool | `false` | Include by default in new specs |

### Real-world example

Here is the `code-reviewer` extension that ships with Rooben:

```yaml
schema_version: 1
name: code-reviewer
type: agent
version: 1.0.0
author: rooben-community
license: MIT
description: Senior code reviewer specializing in Python and TypeScript
tags:
  - code-review
  - python
  - typescript
  - quality
domain_tags:
  - software
category: builder
use_cases:
  - Automated code review for PRs
  - Code quality assessment
min_rooben_version: 0.1.0
transport: llm
capabilities:
  - python
  - typescript
  - testing
  - code-review
system_capabilities:
  filesystem:
    enabled: true
    mode: readwrite
  shell:
    enabled: true
max_concurrency: 2
max_context_tokens: 200000
prompt_template: |
  You are a senior code reviewer. Focus on:
  - Code correctness and edge cases
  - Security vulnerabilities
  - Performance implications
  - Maintainability and readability
  Provide specific, actionable feedback.
is_default: false
max_turns: 25
```

---

## Budget & Concurrency

### Per-agent budget

Each agent can have an `AgentBudget` that constrains its resource usage:

```yaml
budget:
  max_tokens: 32768        # Max LLM tokens per task
  max_tasks: 10            # Max total tasks this agent handles
  max_wall_seconds: 600    # Timeout in seconds
  max_retries_per_task: 3  # Retry limit on failure (default: 3)
```

- **`max_tokens`** -- Caps the LLM output token budget for MCP/LLM agents. Defaults to `16384` if not set.
- **`max_wall_seconds`** -- Used as the timeout for HTTP and subprocess agents. Defaults to `300` (5 minutes).
- **`max_retries_per_task`** -- How many times a failed task is retried before being marked as permanently failed.

### Global budget

The specification also supports a global budget that applies across all agents:

```yaml
global_budget:
  max_total_tokens: 500000
  max_total_tasks: 50
  max_wall_seconds: 3600
  max_concurrent_agents: 5   # default: 5
```

### Concurrency

The `max_concurrency` field on each agent (default `1`) controls how many tasks can run on that agent simultaneously. The `AgentRegistry` enforces this using asyncio semaphores:

```python
# Internal: how the registry enforces concurrency
semaphore = registry.get_semaphore("backend-dev")
async with semaphore:
    result = await agent.execute(task)
```

Setting `max_concurrency: 1` (the default) means tasks for that agent run sequentially. For stateless agents (HTTP, subprocess), you can safely increase this. For LLM/MCP agents, higher concurrency means more parallel LLM calls and higher cost.

---

## Example: Simple HTTP Agent

This example shows a minimal FastAPI service that Rooben can call as an HTTP agent.

### The server

```python
# http_agent_server.py
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class TaskPayload(BaseModel):
    id: str
    description: str
    acceptance_criteria: list[str] = []
    context: str = ""

class TaskResponse(BaseModel):
    output: str
    artifacts: dict[str, str] = {}
    error: str | None = None

@app.post("/execute")
async def execute(task: TaskPayload) -> TaskResponse:
    # Your logic here
    result_text = f"Analyzed: {task.description}"

    return TaskResponse(
        output=result_text,
        artifacts={"analysis.md": f"# Analysis\n\n{result_text}"},
    )

@app.get("/health")
async def health():
    return {"status": "ok"}
```

Run it:

```bash
uvicorn http_agent_server:app --port 8080
```

### The spec entry

```yaml
agents:
  - id: my-http-agent
    name: My HTTP Agent
    transport: http
    description: "Custom analysis agent running as a web service"
    endpoint: "http://localhost:8080"
    capabilities: [analysis]
    max_concurrency: 3
    budget:
      max_wall_seconds: 120
```

The `HTTPAgent` will POST to `http://localhost:8080/execute` with the task as JSON and parse the response into a `TaskResult`.

---

## Example: MCP Agent with Tools

This example configures an MCP agent that can read/write files and run shell commands.

### The spec entry

```yaml
agents:
  - id: fullstack-dev
    name: Fullstack Developer
    transport: mcp
    description: "Builds web applications with file system and shell access"
    capabilities: [python, javascript, html, css, testing]
    max_concurrency: 1
    max_turns: 40
    mcp_servers:
      - name: filesystem
        transport_type: stdio
        command: npx
        args: ["-y", "@anthropic/mcp-filesystem", "/workspace"]
      - name: shell
        transport_type: stdio
        command: npx
        args: ["-y", "@anthropic/mcp-shell"]
    budget:
      max_tokens: 32768
      max_wall_seconds: 900
      max_retries_per_task: 2
```

### Using an SSE-based MCP server

If your MCP server runs as an HTTP service (SSE transport):

```yaml
mcp_servers:
  - name: my-api-tools
    transport_type: sse
    url: "http://localhost:3001/sse"
    headers:
      Authorization: "Bearer ${MY_API_TOKEN}"
```

### Using system capabilities (shorthand)

Instead of manually configuring MCP servers for common capabilities, use `system_capabilities`:

```yaml
agents:
  - id: dev-agent
    name: Developer
    transport: mcp
    description: "General-purpose developer agent"
    capabilities: [python, testing]
    system_capabilities:
      shell:
        enabled: true
        scope: workspace
      memory:
        enabled: true
      fetch:
        enabled: true
```

This is equivalent to manually listing the filesystem, shell, memory, and fetch MCP servers -- the runtime resolves them automatically.

### How the MCP agent loop works

1. The agent receives a task and builds a system prompt listing all available tools from connected MCP servers.
2. The LLM produces JSON with `tool_calls` to invoke tools (read files, run commands, etc.).
3. Tool results are fed back to the LLM for the next turn.
4. The loop continues for up to `max_turns` iterations.
5. When done, the LLM outputs a `final_result` JSON with the output, artifacts, and generated tests.
6. The agent returns a `TaskResult` to the orchestrator.

The agent enforces a one-file-per-turn write discipline and applies context compaction when the conversation exceeds the token threshold.
