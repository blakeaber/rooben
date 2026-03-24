"""Agent implementations — subprocess, HTTP, MCP-backed agents."""

from rooben.agents.protocol import AgentProtocol
from rooben.agents.subprocess_agent import SubprocessAgent
from rooben.agents.http_agent import HTTPAgent
from rooben.agents.mcp_agent import MCPAgent
from rooben.agents.mcp_client import MCPClient, MCPToolInfo
from rooben.agents.registry import AgentRegistry

__all__ = [
    "AgentProtocol",
    "SubprocessAgent",
    "HTTPAgent",
    "MCPAgent",
    "MCPClient",
    "MCPToolInfo",
    "AgentRegistry",
]
