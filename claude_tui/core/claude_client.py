"""Async wrapper around the ``claude`` CLI in streaming-JSON print mode.

We drive the real Claude Code engine as a subprocess::

    claude -p "<prompt>" --output-format stream-json --verbose \
           [--resume <session-id>] [--model <model>] \
           [--permission-mode <mode>]

and yield each parsed JSON event. This gives us Claude Code's full tool/MCP/
permission machinery for free; the TUI is purely a front-end.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator


class ClaudeClient:
    """Spawns and streams from the ``claude`` CLI, one turn at a time."""

    def __init__(self, cli_path: str, cwd: str) -> None:
        self.cli_path = cli_path
        self.cwd = cwd
        self.session_id: str | None = None
        self._proc: asyncio.subprocess.Process | None = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    def _build_args(
        self,
        prompt: str,
        model: str,
        permission_mode: str,
        resume: str | None,
    ) -> list[str]:
        args = [
            self.cli_path,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
        ]
        if resume:
            args += ["--resume", resume]
        if model and model != "default":
            args += ["--model", model]
        if permission_mode:
            args += ["--permission-mode", permission_mode]
        return args

    async def stream(
        self,
        prompt: str,
        *,
        model: str = "default",
        permission_mode: str = "default",
        resume: str | None = None,
    ) -> AsyncIterator[dict]:
        """Run one turn and yield parsed events.

        Synthetic events ``{"type": "_spawn-error"|"_error", ...}`` are emitted
        for launch failures and non-zero exits so the UI can surface them.
        """
        args = self._build_args(prompt, model, permission_mode, resume)
        env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "claude-tui"}

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=self.cwd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except (OSError, ValueError) as exc:
            yield {"type": "_spawn-error", "error": str(exc)}
            return

        self._proc = proc
        assert proc.stdout is not None

        stderr_buf = bytearray()

        async def _drain_stderr() -> None:
            if proc.stderr is None:
                return
            async for chunk in proc.stderr:
                stderr_buf.extend(chunk)

        stderr_task = asyncio.create_task(_drain_stderr())

        try:
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", "replace").strip()
                if not text:
                    continue
                try:
                    yield json.loads(text)
                except json.JSONDecodeError:
                    # Non-JSON noise on stdout — pass it through as a notice.
                    yield {"type": "_stdout", "text": text}

            # stdout reached EOF: reap the process and report a non-zero exit.
            # This stays OUTSIDE ``finally`` on purpose — yielding while a
            # generator is being closed (cancel/exception) raises GeneratorExit,
            # which would skip the cleanup below and wedge ``is_running`` True.
            await proc.wait()
            await stderr_task
            if proc.returncode not in (0, None):
                yield {
                    "type": "_error",
                    "returncode": proc.returncode,
                    "stderr": stderr_buf.decode("utf-8", "replace").strip(),
                }
        finally:
            # Runs on normal completion AND when the consumer cancels/closes the
            # generator. No ``yield`` here, so cleanup always completes.
            if proc.returncode is None:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
            if not stderr_task.done():
                stderr_task.cancel()
            if self._proc is proc:
                self._proc = None

    def cancel(self) -> bool:
        """Terminate the in-flight turn, if any. Returns True if it acted."""
        proc = self._proc
        if proc is not None and proc.returncode is None:
            try:
                proc.terminate()
            except ProcessLookupError:
                return False
            return True
        return False
