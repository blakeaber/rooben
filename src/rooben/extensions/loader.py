"""Extension loader -- discovers and registers extensions from Tier 1 directory and user installs."""

from __future__ import annotations

import logging
from pathlib import Path

from rooben.extensions.manifest import ExtensionManifest, ExtensionType, load_manifest

logger = logging.getLogger("rooben.extensions")


def _find_extension_dirs(base: Path) -> list[Path]:
    """Find all directories containing rooben-extension.yaml under base."""
    if not base.exists():
        return []
    results = []
    for yaml_file in base.rglob("rooben-extension.yaml"):
        results.append(yaml_file.parent)
    return sorted(results)


def _find_tier1_dir() -> Path | None:
    """Locate the bundled extensions/ directory.

    Checks in order:
    1. ROOBEN_EXTENSIONS_DIR env var (explicit override)
    2. Relative to this source file (development: repo checkout)
    3. /app/extensions (Docker container convention)
    4. CWD / extensions (fallback)
    """
    from rooben.config import get_settings

    env_dir = get_settings().rooben_extensions_dir or None
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            return p

    # Development layout: src/rooben/extensions/loader.py → ../../../../extensions
    source_relative = Path(__file__).resolve().parent.parent.parent.parent / "extensions"
    if source_relative.exists():
        return source_relative

    # Docker layout: /app/extensions
    docker_path = Path("/app/extensions")
    if docker_path.exists():
        return docker_path

    # CWD fallback
    cwd_path = Path.cwd() / "extensions"
    if cwd_path.exists():
        return cwd_path

    return None


def load_tier1_extensions() -> list[ExtensionManifest]:
    """Load Tier 1 (bundled) extensions from the extensions/ directory."""
    extensions_dir = _find_tier1_dir()
    if extensions_dir is None:
        return []
    manifests = []
    for ext_dir in _find_extension_dirs(extensions_dir):
        try:
            manifest = load_manifest(ext_dir)
            manifests.append(manifest)
        except Exception as exc:
            logger.warning("extension.tier1_load_failed", extra={"dir": str(ext_dir), "error": str(exc)})
    return manifests


def load_installed_extensions() -> list[ExtensionManifest]:
    """Load user-installed extensions from .rooben/extensions/."""
    install_dir = Path(".rooben/extensions")
    manifests = []
    for ext_dir in _find_extension_dirs(install_dir):
        try:
            manifest = load_manifest(ext_dir)
            manifests.append(manifest)
        except Exception as exc:
            logger.warning("extension.installed_load_failed", extra={"dir": str(ext_dir), "error": str(exc)})
    return manifests


def load_all_extensions() -> list[ExtensionManifest]:
    """Load all extensions (Tier 1 + installed)."""
    return load_tier1_extensions() + load_installed_extensions()


def register_extensions(manifests: list[ExtensionManifest], integration_registry=None) -> None:
    """Register extension manifests into the appropriate registries.

    For integration-type extensions, converts to IntegrationDefinition and registers.
    For agent-type extensions, stores as presets for later use.
    """
    if integration_registry is None:
        return


    for manifest in manifests:
        if manifest.type == ExtensionType.INTEGRATION:
            try:
                _register_integration_extension(manifest, integration_registry)
                logger.info("extension.registered", extra={"name": manifest.name, "type": "integration"})
            except Exception as exc:
                logger.warning("extension.register_failed", extra={"name": manifest.name, "error": str(exc)})


def _register_integration_extension(manifest: ExtensionManifest, registry) -> None:
    """Register an integration extension into the IntegrationRegistry."""
    import re

    from rooben.agents.integrations import IntegrationDefinition
    from rooben.spec.models import MCPServerConfig, MCPTransportType

    env_names = [e.name for e in manifest.required_env]

    def _make_factory(servers_config, required_env_names):
        def factory(workspace_dir: str):
            from rooben.agents.integrations import _gateway_config, _substitute_env_vars, _use_gateway

            configs = []
            for s in servers_config:
                transport = MCPTransportType(s.transport_type)

                # Gateway mode: rewrite stdio/npx to SSE gateway config
                if _use_gateway() and transport == MCPTransportType.STDIO and s.command == "npx":
                    npx_args = s.args or []
                    npx_package = ""
                    extra_args: list[str] = []
                    for a in npx_args:
                        if a in ("-y", "--yes"):
                            continue
                        if not npx_package:
                            npx_package = a
                        else:
                            resolved = _substitute_env_vars(str(a))
                            resolved = resolved.replace("{workspace_dir}", workspace_dir)
                            extra_args.append(resolved)

                    extra_env: dict[str, str] = {}
                    for k, v in s.env.items():
                        resolved_v = _substitute_env_vars(str(v))
                        if resolved_v:
                            extra_env[k] = resolved_v

                    gw = _gateway_config(
                        s.name,
                        npx_package,
                        required_env_names,
                        extra_args=extra_args or None,
                        extra_env=extra_env or None,
                    )
                    configs.extend(gw)
                    continue

                args = []
                for arg in s.args:
                    arg = re.sub(
                        r"\$\{(\w+)\}",
                        lambda m: __import__("os").environ.get(m.group(1), ""),
                        str(arg),
                    )
                    arg = arg.replace("{workspace_dir}", workspace_dir)
                    args.append(arg)
                env = {}
                for k, v in s.env.items():
                    env[k] = re.sub(
                        r"\$\{(\w+)\}",
                        lambda m: __import__("os").environ.get(m.group(1), ""),
                        str(v),
                    )
                configs.append(MCPServerConfig(
                    name=s.name,
                    transport_type=transport,
                    command=s.command,
                    args=args,
                    env=env,
                    url=s.url,
                ))
            return configs
        return factory

    definition = IntegrationDefinition(
        name=manifest.name,
        description=manifest.description,
        domain_tags=manifest.domain_tags,
        cost_tier=manifest.cost_tier,
        mcp_server_factory=_make_factory(manifest.servers, env_names),
        required_env=env_names,
        source="extension",
        author=manifest.author,
        version=manifest.version,
    )
    registry.register(definition)


def validate_extension_readiness(name: str) -> dict:
    """Check if an extension's runtime dependencies are satisfied.

    Returns {"ready": bool, "checks": [{"check": str, "passed": bool, "message": str}]}

    Validation is type-aware and transitive:
    - Integration: checks required_env vars and server command binaries
    - Agent: if it references an integration, validates that integration transitively
    - Template: validates all entries in requires, template_input_sources, and template_agents
    """
    import os
    import shutil

    manifests = load_all_extensions()
    manifest_map = {m.name: m for m in manifests}
    manifest = manifest_map.get(name)

    if not manifest:
        return {"ready": False, "checks": [{"check": "manifest", "passed": False, "message": f"Extension '{name}' not found"}]}

    checks: list[dict] = []

    def _validate_integration(m: ExtensionManifest) -> list[dict]:
        """Validate an integration-type manifest."""
        from rooben.agents.integrations import _credential_cache

        results = []
        for env in m.required_env:
            present = bool(os.environ.get(env.name)) or (env.name in _credential_cache)
            source = "env" if os.environ.get(env.name) else ("stored" if env.name in _credential_cache else "missing")
            results.append({
                "check": f"env:{env.name}",
                "passed": present,
                "message": f"{'Configured' if present else 'Missing'}: {env.name}" + (f" (source: {source})" if present else ""),
            })
        for server in m.servers:
            if server.command:
                found = shutil.which(server.command) is not None
                results.append({
                    "check": f"binary:{server.command}",
                    "passed": found,
                    "message": f"{'Found' if found else 'Not found'}: {server.command}",
                })
        return results

    if manifest.type == ExtensionType.INTEGRATION:
        checks = _validate_integration(manifest)

    elif manifest.type == ExtensionType.AGENT:
        checks.append({"check": "agent:self", "passed": True, "message": "Agent manifest valid"})
        if manifest.integration:
            dep = manifest_map.get(manifest.integration)
            if dep and dep.type == ExtensionType.INTEGRATION:
                dep_checks = _validate_integration(dep)
                checks.extend(dep_checks)
            elif not dep:
                checks.append({
                    "check": f"integration:{manifest.integration}",
                    "passed": False,
                    "message": f"Integration '{manifest.integration}' not found",
                })

    elif manifest.type == ExtensionType.TEMPLATE:
        checks.append({"check": "template:self", "passed": True, "message": "Template manifest valid"})
        # Check requires (integration dependencies)
        for req_name in manifest.requires:
            dep = manifest_map.get(req_name)
            if dep and dep.type == ExtensionType.INTEGRATION:
                dep_checks = _validate_integration(dep)
                checks.extend(dep_checks)
            elif not dep:
                checks.append({
                    "check": f"integration:{req_name}",
                    "passed": False,
                    "message": f"Required integration '{req_name}' not found",
                })
        # Check template_input_sources
        for src in manifest.template_input_sources:
            int_name = src.get("integration", "")
            if int_name:
                dep = manifest_map.get(int_name)
                if dep and dep.type == ExtensionType.INTEGRATION:
                    dep_checks = _validate_integration(dep)
                    checks.extend(dep_checks)
                elif not dep:
                    checks.append({
                        "check": f"integration:{int_name}",
                        "passed": False,
                        "message": f"Input source integration '{int_name}' not found",
                    })
        # Check template_agents
        for agent in manifest.template_agents:
            int_name = agent.get("integration", "")
            if int_name:
                dep = manifest_map.get(int_name)
                if dep and dep.type == ExtensionType.INTEGRATION:
                    dep_checks = _validate_integration(dep)
                    checks.extend(dep_checks)
                else:
                    checks.append({
                        "check": f"agent:{agent.get('name', 'unknown')}",
                        "passed": True if not dep else True,
                        "message": "No integration dependency" if not dep else "Agent ready",
                    })
            else:
                checks.append({
                    "check": f"agent:{agent.get('name', 'unknown')}",
                    "passed": True,
                    "message": "No integration dependency",
                })

    # Deduplicate checks by check name
    seen = set()
    deduped = []
    for c in checks:
        if c["check"] not in seen:
            seen.add(c["check"])
            deduped.append(c)

    ready = all(c["passed"] for c in deduped) if deduped else True
    return {"ready": ready, "checks": deduped}


def get_all_extension_metadata() -> list[dict]:
    """Get metadata for all extensions (for API responses and refinement context).

    Includes ``ready`` (bool) and ``installed`` fields from validation and
    installer checks so consumers can display readiness without extra calls.
    """
    from rooben.extensions.installer import is_installed

    manifests = load_all_extensions()
    result = []
    for m in manifests:
        readiness = validate_extension_readiness(m.name)
        result.append({
            "name": m.name,
            "type": m.type.value,
            "description": m.description,
            "tags": m.tags,
            "domain_tags": m.domain_tags,
            "category": m.category,
            "version": m.version,
            "author": m.author,
            "use_cases": m.use_cases,
            "ready": readiness["ready"],
            "installed": is_installed(m.name),
            "checks": readiness["checks"],
        })
    return result
