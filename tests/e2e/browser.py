"""Python wrapper for the Vercel agent-browser CLI."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field


@dataclass
class Snapshot:
    """Parsed agent-browser snapshot output."""

    raw: str

    def contains(self, text: str, case_sensitive: bool = False) -> bool:
        hay = self.raw if case_sensitive else self.raw.lower()
        needle = text if case_sensitive else text.lower()
        return needle in hay

    def not_contains(self, text: str, case_sensitive: bool = False) -> bool:
        return not self.contains(text, case_sensitive)

    def ref_for(self, pattern: str) -> str | None:
        """Find the @eN ref for an element matching a pattern (case-insensitive)."""
        import re

        for line in self.raw.splitlines():
            if pattern.lower() in line.lower():
                m = re.search(r"\[ref=(e\d+)\]", line)
                if m:
                    return m.group(1)
        return None

    def ref_for_button(self, label: str) -> str | None:
        return self.ref_for(f'button "{label}"')

    def refs_for_button(self, label: str) -> list[str]:
        """Find ALL @eN refs for buttons matching a label."""
        import re

        pattern = f'button "{label}"'
        refs = []
        for line in self.raw.splitlines():
            if pattern.lower() in line.lower():
                m = re.search(r"\[ref=(e\d+)\]", line)
                if m:
                    refs.append(m.group(1))
        return refs

    def ref_for_link(self, label: str) -> str | None:
        return self.ref_for(f'link "{label}')

    def ref_for_textbox(self, placeholder: str) -> str | None:
        return self.ref_for(f'textbox "{placeholder}')


@dataclass
class Browser:
    """Stateful wrapper around agent-browser CLI."""

    base_url: str = "http://localhost:3000"
    timeout: int = 15
    headed: bool = field(default=False, init=False)
    _open: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self.headed = os.environ.get("AGENT_BROWSER_HEADED", "").lower() in ("1", "true", "yes")

    # ── helpers ────────────────────────────────────────────────────

    def _run(self, *args: str, timeout: int | None = None) -> str:
        t = timeout or self.timeout
        cmd = ["agent-browser"]
        if self.headed:
            cmd.append("--headed")
        cmd.extend(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=t,
        )
        # agent-browser writes output to stdout; errors/status to stderr
        return (result.stdout + result.stderr).strip()

    # ── navigation ────────────────────────────────────────────────

    def open(self, path: str, *, wait_ms: int = 2000) -> str:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        out = self._run("open", url)
        self._open = True
        if wait_ms:
            import time
            time.sleep(wait_ms / 1000)
        return out

    def get_url(self) -> str:
        return self._run("get", "url")

    # ── inspection ────────────────────────────────────────────────

    def snapshot(self) -> Snapshot:
        return Snapshot(raw=self._run("snapshot"))

    def find(self, kind: str, value: str) -> str:
        return self._run("find", kind, value)

    def screenshot(self, path: str) -> str:
        return self._run("screenshot", path)

    # ── interaction ───────────────────────────────────────────────

    def click(self, ref: str, timeout: int = 30) -> str:
        ref_str = ref if ref.startswith("@") else f"@{ref}"
        return self._run("click", ref_str, timeout=timeout)

    def fill(self, ref: str, text: str) -> str:
        ref_str = ref if ref.startswith("@") else f"@{ref}"
        return self._run("fill", ref_str, text)

    def type_text(self, ref: str, text: str) -> str:
        ref_str = ref if ref.startswith("@") else f"@{ref}"
        return self._run("type", ref_str, text)

    # ── wait ──────────────────────────────────────────────────────

    def wait(self, ms: int = 1000) -> None:
        import time
        time.sleep(ms / 1000)

    def wait_for_text(self, text: str, timeout_ms: int = 10000) -> Snapshot:
        """Poll snapshot until text appears or timeout."""
        import time

        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            snap = self.snapshot()
            if snap.contains(text):
                return snap
            time.sleep(0.5)
        raise TimeoutError(
            f"Text '{text}' not found within {timeout_ms}ms. "
            f"Last snapshot:\n{snap.raw[:500]}"
        )

    # ── evaluation ────────────────────────────────────────────────

    def eval(self, js: str) -> str:
        return self._run("eval", js, timeout=30)

    @staticmethod
    def _parse_eval_result(result: str) -> str:
        """Extract the meaningful value from agent-browser eval output.

        agent-browser may wrap the result in quotes or include extra whitespace.
        """
        text = result.strip()
        # If the entire output is a JSON-encoded string (starts with "), unwrap it
        if text.startswith('"') and text.endswith('"'):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        return text

    def fetch_status(self, path: str, method: str = "GET", body: dict | None = None) -> int:
        """Execute a fetch in browser context and return HTTP status code."""
        opts = f"{{method:'{method}'"
        if body is not None:
            opts += f",headers:{{'Content-Type':'application/json'}},body:JSON.stringify({json.dumps(body)})"
        opts += "}"
        js = f"fetch('{path}',{opts}).then(r=>r.status.toString())"
        result = self._parse_eval_result(self.eval(js))
        # Extract the numeric status from the output
        for token in result.split():
            if token.isdigit():
                return int(token)
        raise ValueError(f"Could not parse status from: {result}")

    def fetch_json(self, path: str, method: str = "GET", body: dict | None = None) -> dict:
        """Execute a fetch in browser context and return parsed JSON."""
        opts = f"{{method:'{method}'"
        if body is not None:
            opts += f",headers:{{'Content-Type':'application/json'}},body:JSON.stringify({json.dumps(body)})"
        opts += "}"
        js = f"fetch('{path}',{opts}).then(r=>r.json()).then(d=>JSON.stringify(d))"
        raw = self._parse_eval_result(self.eval(js))
        # Try parsing the whole thing first
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
        # Fallback: find a JSON object/array in the output
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("{") or line.startswith("["):
                return json.loads(line)
        raise ValueError(f"Could not parse JSON from: {raw[:500]}")

    # ── lifecycle ─────────────────────────────────────────────────

    def close(self) -> str:
        if self._open:
            self._open = False
            return self._run("close")
        return ""
