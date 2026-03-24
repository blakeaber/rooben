"""Credential API endpoints for integration credential management."""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from rooben.dashboard.deps import get_deps, user_context as _user_context
from rooben.dashboard.queries import credentials as cred_queries

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


class CreateCredentialRequest(BaseModel):
    integration_name: str
    env_var_name: str
    value: str
    credential_type: str = "integration"


class TestLLMRequest(BaseModel):
    model: str | None = None


@router.get("")
async def list_credentials(request: Request, integration: str | None = None):
    """List credentials (masked values)."""
    deps = get_deps()
    creds = await cred_queries.list_credentials(
        deps.pool, integration, user_context=_user_context(request),
    )
    return {"credentials": creds}


@router.post("")
async def create_credential(req: CreateCredentialRequest):
    """Create or update a credential."""
    deps = get_deps()
    cred_id = str(uuid.uuid4())
    cred = await cred_queries.upsert_credential(
        deps.pool, cred_id, req.integration_name, req.env_var_name, req.value,
        credential_type=req.credential_type,
    )
    # Refresh cache
    from rooben.agents.integrations import populate_credential_cache
    await populate_credential_cache(deps.pool)
    return {"created": True, **cred}


@router.delete("/{credential_id}")
async def delete_credential(credential_id: str):
    """Delete a credential."""
    deps = get_deps()
    deleted = await cred_queries.delete_credential(deps.pool, credential_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Credential not found")
    # Refresh cache
    from rooben.agents.integrations import populate_credential_cache
    await populate_credential_cache(deps.pool)
    return {"deleted": True}


def _credential_source(env_var: str) -> str:
    """Determine source of a credential: env, stored, or missing."""
    from rooben.agents.integrations import _credential_cache
    if os.environ.get(env_var):
        return "env"
    if env_var in _credential_cache:
        return "stored"
    return "missing"


@router.get("/status")
async def credential_status():
    """Return status of all known API keys — derived from the integration registry."""
    from rooben.dashboard.orchestrator_factory import build_integration_registry

    registry = build_integration_registry()
    keys: list[dict] = []
    seen: set[str] = set()

    for integ in registry.list_all():
        for env_var in integ.required_env:
            if env_var in seen:
                continue
            seen.add(env_var)
            source = _credential_source(env_var)
            keys.append({
                "env_var": env_var,
                "integration": integ.name,
                "credential_type": integ.kind if integ.kind == "llm_provider" else "integration",
                "available": source != "missing",
                "source": source,
            })

    return {"keys": keys}


@router.post("/test/{integration_name}")
async def test_integration_credentials(integration_name: str):
    """Test integration with stored credentials."""
    from rooben.agents.integrations import _use_gateway
    from rooben.dashboard.orchestrator_factory import build_integration_registry

    registry = build_integration_registry()
    tk = registry.get(integration_name)
    if not tk:
        raise HTTPException(
            status_code=404, detail=f"Integration '{integration_name}' not found"
        )

    checks = []
    for env_var in tk.required_env:
        source = _credential_source(env_var)
        present = source != "missing"
        checks.append({
            "check": f"env:{env_var}",
            "passed": present,
            "message": f"{'Available' if present else 'Missing'}: {env_var} (source: {source})",
        })

    # Check server availability
    try:
        servers = tk.mcp_server_factory("/tmp/_test")
        if _use_gateway():
            for s in servers:
                checks.append({
                    "check": f"gateway:{s.name}",
                    "passed": s.transport_type.value == "sse" and bool(s.url),
                    "message": f"Gateway route configured for {s.name}",
                })
        else:
            import shutil as _shutil
            for s in servers:
                if s.command:
                    found = _shutil.which(s.command) is not None
                    checks.append({
                        "check": f"binary:{s.command}",
                        "passed": found,
                        "message": f"{'Found' if found else 'Not found'}: {s.command}",
                    })
    except Exception as exc:
        checks.append({
            "check": "server_factory",
            "passed": False,
            "message": f"Error: {exc}",
        })

    all_passed = all(c["passed"] for c in checks)
    return {"name": integration_name, "passed": all_passed, "checks": checks}


@router.post("/test-llm/{provider_name}")
async def test_llm_credential(provider_name: str, req: TestLLMRequest | None = None):
    """Validate an LLM provider key with a minimal API call."""
    from rooben.agents.integrations import resolve_credential
    from rooben.dashboard.orchestrator_factory import build_integration_registry

    registry = build_integration_registry()
    provider_def = registry.get(provider_name)
    if not provider_def or provider_def.kind != "llm_provider":
        raise HTTPException(
            status_code=404, detail=f"LLM provider '{provider_name}' not found"
        )

    checks = []

    # Check credential availability
    if provider_def.required_env:
        env_var = provider_def.required_env[0]
        source = _credential_source(env_var)
        api_key = resolve_credential(env_var)
        checks.append({
            "check": f"credential:{env_var}",
            "passed": bool(api_key),
            "message": f"{'Available' if api_key else 'Missing'}: {env_var} (source: {source})",
        })
        if not api_key:
            return {"name": provider_name, "passed": False, "checks": checks}
    else:
        api_key = ""

    # Determine model
    model = (req and req.model) or None
    if not model:
        from rooben.dashboard.routes.hub import DISPLAY_TYPE_MAP  # noqa: F401
        # Use sensible defaults
        _defaults = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
            "ollama": "llama3.1",
            "bedrock": "anthropic.claude-sonnet-4-20250514-v1:0",
        }
        model = _defaults.get(provider_name, "")

    # Test API connectivity
    try:
        if provider_name == "anthropic":
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            await client.messages.create(
                model=model,
                max_tokens=1,
                messages=[{"role": "user", "content": "hi"}],
            )
            checks.append({
                "check": "api_connectivity",
                "passed": True,
                "message": f"Successfully connected to Anthropic API with model {model}",
            })
        elif provider_name == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            await client.models.list()
            checks.append({
                "check": "api_connectivity",
                "passed": True,
                "message": "Successfully connected to OpenAI API",
            })
        elif provider_name == "ollama":
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://localhost:11434/api/tags", timeout=5)
                resp.raise_for_status()
            checks.append({
                "check": "api_connectivity",
                "passed": True,
                "message": "Ollama server is running",
            })
        elif provider_name == "bedrock":
            # Bedrock uses AWS credentials — just verify the provider can be imported
            try:
                from rooben.planning.bedrock_provider import BedrockProvider  # noqa: F401
                checks.append({
                    "check": "api_connectivity",
                    "passed": True,
                    "message": "Bedrock provider available (AWS credentials validated at runtime)",
                })
            except ImportError:
                checks.append({
                    "check": "api_connectivity",
                    "passed": False,
                    "message": "Bedrock provider not installed (pip install boto3)",
                })
        else:
            checks.append({
                "check": "api_connectivity",
                "passed": False,
                "message": f"Unknown provider: {provider_name}",
            })
    except Exception as exc:
        checks.append({
            "check": "api_connectivity",
            "passed": False,
            "message": f"Connection failed: {exc}",
        })

    all_passed = all(c["passed"] for c in checks)
    return {"name": provider_name, "passed": all_passed, "checks": checks}
