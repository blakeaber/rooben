FROM node:20-alpine
WORKDIR /app

# Install Python for Python-based MCP servers (e.g. mcp-server-fetch)
RUN apk add --no-cache python3 py3-pip && \
    python3 -m pip install --break-system-packages mcp-server-fetch

# npm cache location — matches the persistent volume mount in docker-compose
RUN npm config set cache /root/.npm

COPY package*.json ./
RUN npm install --omit=dev

# Pre-warm ONLY system-level infrastructure packages (always granted to agents).
# External integration packages (brave-search, slack, etc.) are cached dynamically
# via the /warmup endpoint — no hardcoding needed.
RUN npm cache add @modelcontextprotocol/server-filesystem && \
    npm cache add mcp-shell-server && \
    npm cache add @anthropic/mcp-server-memory || true

# Create workspace directory for filesystem server
RUN mkdir -p /app/.rooben/state /app/.rooben/workspaces

COPY . .
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s CMD wget -qO- http://localhost:8080/health || exit 1
CMD ["node", "index.js"]
