# ── API-only image (dashboard runs as a separate service) ─────────────────────
FROM python:3.12-slim AS runtime

RUN groupadd -r rooben && useradd -r -g rooben rooben

# Install gosu for runtime user switching after fixing volume ownership
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (include mcp for agent support)
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY extensions/ ./extensions/
RUN pip install --no-cache-dir ".[dashboard,mcp]" asyncpg

# Create workspace directories
RUN mkdir -p /app/.rooben/state /app/.rooben/workspaces && \
    chown -R rooben:rooben /app

# Entrypoint fixes volume ownership then drops to rooben user
COPY --chmod=755 <<'ENTRYPOINT' /app/entrypoint.sh
#!/bin/sh
# Docker volumes mount as root — fix ownership before dropping privileges
chown -R rooben:rooben /app/.rooben
exec gosu rooben "$@"
ENTRYPOINT

EXPOSE 8420

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8420/api/health')"

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "rooben.dashboard.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8420"]
