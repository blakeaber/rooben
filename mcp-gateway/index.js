/**
 * MCP Gateway — spawns npx MCP server subprocesses per SSE connection.
 *
 * Headers on GET /sse:
 *   X-MCP-Package  — npm package to run (e.g. "@anthropic/mcp-server-brave-search")
 *   X-MCP-Args     — JSON array of extra CLI args (optional)
 *   X-MCP-Env      — base64-encoded JSON object of env vars to inject (optional)
 *
 * The gateway bridges the child's stdio (MCP protocol) to SSE for the API container.
 */

const express = require("express");
const { spawn } = require("child_process");
const crypto = require("crypto");

const app = express();
app.use(express.json());
const PORT = process.env.PORT || 8080;

// Track active sessions for cleanup
const activeSessions = new Map();

// Deduplicate concurrent warmup requests for the same package
const warmupInFlight = new Map();

// Validate npm package names — prevent command injection via spawn/exec.
// Allows scoped (@org/pkg) and unscoped names with dots, hyphens, underscores.
const VALID_PKG_RE = /^(@[\w-]+\/)?[\w][\w._-]*$/;
function isValidPackageName(pkg) {
  return typeof pkg === "string" && pkg.length <= 214 && VALID_PKG_RE.test(pkg);
}

// Python-based MCP servers that should be spawned directly, not via npx
const PYTHON_MCP_SERVERS = new Set([
  "@anthropic/mcp-server-fetch",
  "mcp-server-fetch",
]);

/**
 * Resolve command and args for an MCP server package.
 * Python packages are spawned directly; npm packages via npx.
 */
function resolveSpawnCommand(pkg, extraArgs) {
  if (PYTHON_MCP_SERVERS.has(pkg)) {
    // Python package: spawn the CLI entry point directly
    const cmd = pkg.replace(/^@anthropic\//, "");
    return { cmd, args: [...extraArgs] };
  }
  return { cmd: "npx", args: ["-y", pkg, ...extraArgs] };
}

app.get("/health", (_req, res) => {
  res.json({ status: "ok", sessions: activeSessions.size });
});

/**
 * POST /warmup — pre-cache an npm package without spawning it.
 *
 * Runs `npm cache add <package>` to download the tarball into the npm cache.
 * Subsequent npx spawns will use the cached version. Concurrent requests for
 * the same package are deduplicated.
 *
 * Body: {"package": "@anthropic/mcp-server-brave-search"}
 */
app.post("/warmup", async (req, res) => {
  const pkg = req.body && req.body.package;
  if (!pkg) {
    return res.status(400).json({ error: "Missing 'package' field" });
  }
  if (!isValidPackageName(pkg)) {
    return res.status(400).json({ error: "Invalid package name" });
  }

  // Python packages are pip-installed in the image — nothing to warm up
  if (PYTHON_MCP_SERVERS.has(pkg)) {
    return res.json({ status: "ready", package: pkg, cached: true, duration_ms: 0 });
  }

  // Deduplicate: if already warming up this package, wait for that result
  if (warmupInFlight.has(pkg)) {
    try {
      const result = await warmupInFlight.get(pkg);
      return res.json(result);
    } catch (err) {
      return res.json({ status: "error", package: pkg, error: err.message });
    }
  }

  const startTime = Date.now();
  console.log(`[warmup] Caching: ${pkg}`);

  const promise = new Promise((resolve, reject) => {
    const child = spawn("npm", ["cache", "add", pkg], {
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"],
      timeout: 120000,
    });
    let stderr = "";
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.on("exit", (code) => {
      const duration_ms = Date.now() - startTime;
      console.log(`[warmup] ${pkg}: ${code === 0 ? "cached" : "failed"} (${duration_ms}ms)`);
      if (code === 0) {
        resolve({ status: "ready", package: pkg, cached: true, duration_ms });
      } else {
        reject(new Error(stderr.trim() || `npm cache add exited with code ${code}`));
      }
    });
    child.on("error", reject);
  });

  warmupInFlight.set(pkg, promise);
  try {
    const result = await promise;
    res.json(result);
  } catch (err) {
    res.json({
      status: "error",
      package: pkg,
      error: err.message,
      duration_ms: Date.now() - startTime,
    });
  } finally {
    warmupInFlight.delete(pkg);
  }
});

/**
 * GET /probe — liveness check for an MCP server package.
 *
 * Spawns the package, sends MCP "initialize", waits for response,
 * then kills the process. Returns {alive, server_info, startup_ms} or {alive: false, error}.
 *
 * Headers: same as /sse (X-MCP-Package required, X-MCP-Args/X-MCP-Env optional).
 * Timeout: controlled by X-MCP-Timeout header (default 30s, max 60s).
 */
app.get("/probe", (req, res) => {
  const pkg = req.headers["x-mcp-package"];
  if (!pkg) {
    return res.status(400).json({ error: "X-MCP-Package header required" });
  }
  if (!isValidPackageName(pkg) && !PYTHON_MCP_SERVERS.has(pkg)) {
    return res.status(400).json({ error: "Invalid X-MCP-Package name" });
  }

  let extraArgs = [];
  if (req.headers["x-mcp-args"]) {
    try {
      extraArgs = JSON.parse(req.headers["x-mcp-args"]);
    } catch {
      return res.status(400).json({ error: "Invalid X-MCP-Args JSON" });
    }
  }

  let envVars = {};
  if (req.headers["x-mcp-env"]) {
    try {
      envVars = JSON.parse(
        Buffer.from(req.headers["x-mcp-env"], "base64").toString("utf8")
      );
    } catch {
      return res.status(400).json({ error: "Invalid X-MCP-Env base64 JSON" });
    }
  }

  const timeoutMs = Math.min(
    parseInt(req.headers["x-mcp-timeout"] || "30000", 10),
    60000
  );

  const startTime = Date.now();
  const { cmd, args } = resolveSpawnCommand(pkg, extraArgs);

  console.log(`[probe] Probing: ${cmd} ${args.join(" ")}`);

  const child = spawn(cmd, args, {
    env: { ...process.env, ...envVars },
    stdio: ["pipe", "pipe", "pipe"],
  });

  let responded = false;
  let buffer = "";

  function respond(result) {
    if (responded) return;
    responded = true;
    if (!child.killed) {
      child.kill("SIGTERM");
      setTimeout(() => {
        if (!child.killed) child.kill("SIGKILL");
      }, 2000);
    }
    res.json(result);
  }

  // Set timeout
  const timer = setTimeout(() => {
    respond({
      alive: false,
      error: `Probe timed out after ${timeoutMs}ms`,
      startup_ms: Date.now() - startTime,
    });
  }, timeoutMs);

  // Send MCP initialize request
  const initRequest = JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "initialize",
    params: {
      protocolVersion: "2024-11-05",
      capabilities: {},
      clientInfo: { name: "rooben-probe", version: "1.0.0" },
    },
  });

  // Wait a moment for the process to start, then send initialize
  setTimeout(() => {
    if (!responded && !child.killed) {
      try {
        child.stdin.write(initRequest + "\n");
      } catch (err) {
        clearTimeout(timer);
        respond({
          alive: false,
          error: `Failed to write to process: ${err.message}`,
          startup_ms: Date.now() - startTime,
        });
      }
    }
  }, 500);

  // Read response from stdout
  child.stdout.on("data", (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) {
        try {
          const msg = JSON.parse(line.trim());
          if (msg.id === 1 && msg.result) {
            clearTimeout(timer);
            respond({
              alive: true,
              server_info: msg.result.serverInfo || {},
              startup_ms: Date.now() - startTime,
            });
          } else if (msg.id === 1 && msg.error) {
            clearTimeout(timer);
            respond({
              alive: false,
              error: msg.error.message || "MCP initialize error",
              startup_ms: Date.now() - startTime,
            });
          }
        } catch {
          // Not valid JSON, ignore
        }
      }
    }
  });

  child.stderr.on("data", (chunk) => {
    console.error(`[probe] stderr: ${chunk.toString().trim()}`);
  });

  child.on("error", (err) => {
    clearTimeout(timer);
    respond({
      alive: false,
      error: `Spawn error: ${err.message}`,
      startup_ms: Date.now() - startTime,
    });
  });

  child.on("exit", (code) => {
    clearTimeout(timer);
    if (!responded) {
      respond({
        alive: false,
        error: `Process exited with code ${code} before responding`,
        startup_ms: Date.now() - startTime,
      });
    }
  });

  // Client disconnect cleanup
  req.on("close", () => {
    clearTimeout(timer);
    if (!child.killed) {
      child.kill("SIGTERM");
      setTimeout(() => {
        if (!child.killed) child.kill("SIGKILL");
      }, 2000);
    }
  });
});

app.get("/sse", (req, res) => {
  const pkg = req.headers["x-mcp-package"];
  if (!pkg) {
    return res.status(400).json({ error: "X-MCP-Package header required" });
  }
  if (!isValidPackageName(pkg) && !PYTHON_MCP_SERVERS.has(pkg)) {
    return res.status(400).json({ error: "Invalid X-MCP-Package name" });
  }

  // Parse optional args and env
  let extraArgs = [];
  if (req.headers["x-mcp-args"]) {
    try {
      extraArgs = JSON.parse(req.headers["x-mcp-args"]);
    } catch {
      return res.status(400).json({ error: "Invalid X-MCP-Args JSON" });
    }
  }

  let envVars = {};
  if (req.headers["x-mcp-env"]) {
    try {
      envVars = JSON.parse(
        Buffer.from(req.headers["x-mcp-env"], "base64").toString("utf8")
      );
    } catch {
      return res.status(400).json({ error: "Invalid X-MCP-Env base64 JSON" });
    }
  }

  const sessionId = crypto.randomUUID();
  const { cmd, args } = resolveSpawnCommand(pkg, extraArgs);

  console.log(
    `[${sessionId}] Spawning: ${cmd} ${args.join(" ")} (env keys: ${Object.keys(envVars).join(", ") || "none"})`
  );

  // Spawn the MCP server subprocess
  const child = spawn(cmd, args, {
    env: { ...process.env, ...envVars },
    stdio: ["pipe", "pipe", "pipe"],
  });

  activeSessions.set(sessionId, child);

  // SSE headers
  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
    "X-MCP-Session": sessionId,
  });

  // Send the endpoint event — tells the MCP client where to POST messages
  res.write(`event: endpoint\ndata: /message?session=${sessionId}\n\n`);

  // SSE keepalive — send comment lines every 15s to detect dead connections.
  // SSE comment lines (starting with `:`) are ignored by MCP SDK's SSE client.
  const keepalive = setInterval(() => {
    if (!res.writableEnded) {
      res.write(`: keepalive\n\n`);
    }
  }, 15000);

  // Bridge child stdout → SSE
  let buffer = "";
  child.stdout.on("data", (chunk) => {
    buffer += chunk.toString();
    // MCP stdio uses newline-delimited JSON
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      if (line.trim()) {
        res.write(`event: message\ndata: ${line}\n\n`);
      }
    }
  });

  child.stderr.on("data", (chunk) => {
    console.error(`[${sessionId}] stderr: ${chunk.toString().trim()}`);
  });

  child.on("error", (err) => {
    console.error(`[${sessionId}] spawn error:`, err.message);
    res.write(
      `event: error\ndata: ${JSON.stringify({ error: err.message })}\n\n`
    );
    cleanup();
  });

  child.on("exit", (code) => {
    console.log(`[${sessionId}] exited with code ${code}`);
    res.write(
      `event: error\ndata: ${JSON.stringify({ error: `Process exited with code ${code}` })}\n\n`
    );
    cleanup();
  });

  function cleanup() {
    clearInterval(keepalive);
    activeSessions.delete(sessionId);
    if (!child.killed) {
      child.kill("SIGTERM");
      setTimeout(() => {
        if (!child.killed) child.kill("SIGKILL");
      }, 3000);
    }
    res.end();
  }

  // Client disconnect → kill subprocess
  req.on("close", () => {
    console.log(`[${sessionId}] client disconnected`);
    cleanup();
  });
});

// POST /message — forward messages from MCP client to child stdin
app.post("/message", express.json({ limit: "10mb" }), (req, res) => {
  const sessionId = req.query.session;
  if (!sessionId) {
    return res.status(400).json({ error: "session query parameter required" });
  }

  const child = activeSessions.get(sessionId);
  if (!child) {
    return res.status(404).json({ error: "session not found" });
  }

  try {
    const message = JSON.stringify(req.body) + "\n";
    child.stdin.write(message);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, () => {
  console.log(`MCP Gateway listening on port ${PORT}`);
});
