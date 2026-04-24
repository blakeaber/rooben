#!/usr/bin/env python3
"""Runnable wrapper for the bundled demo orchestration.

The actual demo lives at `src/rooben/_demo_orchestration.py` so it ships with
`pip install rooben`. This wrapper lets a repo clone run the demo directly:

    python examples/demo_orchestration.py

For the packaged CLI invocation use:

    rooben demo
"""
from __future__ import annotations

import asyncio

from rooben._demo_orchestration import main


if __name__ == "__main__":
    asyncio.run(main())
