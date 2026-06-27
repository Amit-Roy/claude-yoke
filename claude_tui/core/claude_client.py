"""Async wrapper around the ``claude`` CLI in bidirectional stream-json mode.

We drive the real Claude Code engine as a subprocess::

    claude --input-format stream-json --output-format stream-json --verbose \
           --permission-prompt-tool stdio \
           [--resume <session-id>] [--model <model>] [--permission-mode <mode>]

The user's turn is written to the process's stdin as a stream-json ``user``
message (rather than passed as ``-p``), which keeps stdin open so the CLI can
ask us to approve tools mid-turn. Tool-permission prompts arrive as
``control_request`` events; we surface them to the UI and write the user's
answer back as a ``control_response``. This is what makes questions/permission
prompts "bubble up" instead of being silently auto-denied.

The wire shapes below were captured from claude 2.1.172.
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
        model: str,
        permission_mode: str,
        resume: str | None,
    ) -> list[str]:
        args = [
            self.cli_path,
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            # Route tool-permission prompts to us over the control protocol
            # instead of auto-denying them in headless mode.
            "--permission-prompt-tool",
            "stdio",
        ]
        if resume:
            args += ["--resume", resume]
        if model and model != "default":
            args += ["--model", model]
        if permission_mode:
            args += ["--permission-mode", permission_mode]
        return args

    async def _write_json(self, proc: asyncio.subprocess.Process, obj: dict) -> None:
        """Write one stream-json line to the process's stdin, tolerantly."""
        if proc.stdin is None:
            return
        try:
            proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    async def stream(
        self,
        prompt: str,
        *,
        model: str = "default",
        permission_mode: str = "default",
        resume: str | None = None,
    ) -> AsyncIterator[dict]:
        """Run one turn and yield parsed events.

        A ``control_request`` (tool permission) is surfaced as a synthetic
        ``{"type": "_permission", "request": <event>}`` event; the caller is
        expected to answer it via :meth:`respond_permission` before consuming
        the next event. Launch/exit failures arrive as ``_spawn-error`` /
        ``_error`` events.
        """
        args = self._build_args(model, permission_mode, resume)
        env = {**os.environ, "CLAUDE_CODE_ENTRYPOINT": "claude-tui"}

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=self.cwd,
                stdin=asyncio.subprocess.PIPE,
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

        # Send the user's turn as a stream-json message.
        await self._write_json(
            proc,
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                },
            },
        )

        try:
            while True:
                raw = await proc.stdout.readline()
                if not raw:
                    break
                text = raw.decode("utf-8", "replace").strip()
                if not text:
                    continue
                try:
                    event = json.loads(text)
                except json.JSONDecodeError:
                    yield {"type": "_stdout", "text": text}
                    continue

                if event.get("type") == "control_request":
                    # Permission/elicitation request — hand it to the UI.
                    yield {"type": "_permission", "request": event}
                    continue

                yield event
                if event.get("type") == "result":
                    # One turn per process: stop reading once the turn resolves.
                    break

            # Close stdin so the streaming-input process exits, then reap it.
            # Kept OUTSIDE ``finally`` so a yield during cancel can't skip the
            # cleanup that clears ``_proc`` (which would wedge ``is_running``).
            if proc.stdin is not None and not proc.stdin.is_closing():
                try:
                    proc.stdin.close()
                except Exception:
                    pass
            await proc.wait()
            await stderr_task
            if proc.returncode not in (0, None):
                yield {
                    "type": "_error",
                    "returncode": proc.returncode,
                    "stderr": stderr_buf.decode("utf-8", "replace").strip(),
                }
        finally:
            if proc.returncode is None:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
            if not stderr_task.done():
                stderr_task.cancel()
            if self._proc is proc:
                self._proc = None

    async def respond_permission(
        self,
        request_id: str,
        *,
        allow: bool,
        updated_input: dict | None = None,
        message: str | None = None,
    ) -> None:
        """Answer a ``can_use_tool`` control request over stdin.

        Allow must echo the (possibly edited) tool input back as
        ``updatedInput`` — without it the CLI reports a validation error and
        the tool never runs.
        """
        proc = self._proc
        if proc is None or proc.stdin is None or proc.stdin.is_closing():
            return
        if allow:
            inner = {"behavior": "allow", "updatedInput": updated_input or {}}
        else:
            inner = {"behavior": "deny", "message": message or "Denied by the user."}
        await self._write_json(
            proc,
            {
                "type": "control_response",
                "response": {
                    "subtype": "success",
                    "request_id": request_id,
                    "response": inner,
                },
            },
        )

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
