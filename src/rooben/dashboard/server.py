"""Uvicorn launch logic for the dashboard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_dashboard(host: str = "127.0.0.1", port: int = 8420, dev: bool = False) -> None:
    """Start the dashboard API server, optionally with Next.js dev server."""
    import uvicorn

    dashboard_dir = Path(__file__).resolve().parents[3] / "dashboard"
    static_dir = str(dashboard_dir / "out") if not dev else None

    nextjs_proc = None
    if dev and dashboard_dir.exists():
        print(f"Starting Next.js dev server from {dashboard_dir}...")
        nextjs_proc = subprocess.Popen(
            [sys.executable.replace("python", "npx"), "next", "dev", "--port", "3000"],
            cwd=str(dashboard_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    try:
        print(f"Starting Rooben Dashboard API on http://{host}:{port}")
        if dev:
            print("Next.js frontend at http://localhost:3000")

        from rooben.dashboard.app import create_app

        app = create_app(static_dir=static_dir)
        uvicorn.run(app, host=host, port=port)
    finally:
        if nextjs_proc:
            nextjs_proc.terminate()
            nextjs_proc.wait()
