"""Read and summarize Claude Code session transcripts (``*.jsonl``).

Sessions live under ``~/.claude/projects/<encoded-cwd>/<session-id>.jsonl``.
Each line is a JSON record; the types we care about are ``user``,
``assistant`` (carries ``message.model`` and ``message.usage``) and
``ai-title`` / ``summary`` (a human-friendly label).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _human_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    hours, rem = divmod(seconds, 3600)
    return f"{hours}h {rem // 60}m"


def _human_size(num: int) -> str:
    value = float(num)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f}{unit}" if unit == "B" else f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}GB"


@dataclass
class SessionMeta:
    """Summary metadata for one session transcript."""

    path: Path
    session_id: str
    title: str = "(untitled)"
    model: str = "?"
    created: datetime | None = None
    updated: datetime | None = None
    size_bytes: int = 0
    message_count: int = 0
    context_tokens: int = 0  # input + cache from the last assistant turn
    output_tokens: int = 0  # cumulative output across the session
    git_branch: str = ""

    @property
    def duration_str(self) -> str:
        if self.created and self.updated:
            return _human_duration((self.updated - self.created).total_seconds())
        return "-"

    @property
    def size_str(self) -> str:
        return _human_size(self.size_bytes)

    @property
    def short_model(self) -> str:
        m = self.model.replace("claude-", "")
        return m or "?"

    @property
    def updated_str(self) -> str:
        return self.updated.strftime("%Y-%m-%d %H:%M") if self.updated else "-"


def summarize_session(path: Path) -> SessionMeta:
    """Build a :class:`SessionMeta` by scanning one ``.jsonl`` file."""
    meta = SessionMeta(
        path=path,
        session_id=path.stem,
        size_bytes=path.stat().st_size if path.exists() else 0,
    )
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    title_from_user: str | None = None

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                rtype = rec.get("type")

                if rtype in ("ai-title", "summary"):
                    title = rec.get("aiTitle") or rec.get("summary")
                    if title:
                        meta.title = str(title).strip()

                if rtype in ("user", "assistant"):
                    meta.message_count += 1
                    ts = _parse_ts(rec.get("timestamp"))
                    if ts:
                        first_ts = ts if first_ts is None else min(first_ts, ts)
                        last_ts = ts if last_ts is None else max(last_ts, ts)
                    if rec.get("gitBranch"):
                        meta.git_branch = rec["gitBranch"]

                if rtype == "user" and title_from_user is None:
                    title_from_user = _first_user_text(rec)

                if rtype == "assistant":
                    msg = rec.get("message", {}) or {}
                    if msg.get("model"):
                        meta.model = msg["model"]
                    usage = msg.get("usage") or {}
                    meta.output_tokens += int(usage.get("output_tokens", 0) or 0)
                    ctx = (
                        int(usage.get("input_tokens", 0) or 0)
                        + int(usage.get("cache_read_input_tokens", 0) or 0)
                        + int(usage.get("cache_creation_input_tokens", 0) or 0)
                    )
                    if ctx:
                        meta.context_tokens = ctx
    except OSError:
        pass

    meta.created = first_ts
    meta.updated = last_ts or (
        datetime.fromtimestamp(path.stat().st_mtime) if path.exists() else None
    )
    if meta.title == "(untitled)" and title_from_user:
        meta.title = title_from_user[:80]
    return meta


def _first_user_text(rec: dict) -> str | None:
    """Extract a short plain-text label from a user record, skipping meta."""
    if rec.get("isMeta"):
        return None
    content = (rec.get("message") or {}).get("content")
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                break
    text = text.strip()
    # Skip command/caveat wrappers that Claude Code injects.
    if not text or text.startswith("<"):
        return None
    return " ".join(text.split())


def load_sessions(project_dir: Path) -> list[SessionMeta]:
    """Return all sessions in *project_dir*, newest first."""
    if not project_dir.exists():
        return []
    metas = [
        summarize_session(p)
        for p in project_dir.glob("*.jsonl")
        if p.is_file()
    ]
    metas.sort(key=lambda m: m.updated or datetime.min, reverse=True)
    return metas


@dataclass
class TranscriptMessage:
    """A normalized message ready for rendering in the chat log."""

    role: str  # "user" | "assistant" | "tool_use" | "tool_result" | "system"
    text: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    is_error: bool = False


def load_transcript(path: Path) -> tuple[list[TranscriptMessage], SessionMeta]:
    """Parse a session file into renderable messages plus its metadata."""
    messages: list[TranscriptMessage] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                messages.extend(_records_to_messages(rec))
    except OSError:
        pass
    return messages, summarize_session(path)


def _records_to_messages(rec: dict) -> list[TranscriptMessage]:
    rtype = rec.get("type")
    if rtype not in ("user", "assistant"):
        return []
    if rec.get("isMeta"):
        return []

    out: list[TranscriptMessage] = []
    msg = rec.get("message") or {}
    role = msg.get("role", rtype)
    content = msg.get("content")

    if isinstance(content, str):
        text = content.strip()
        if text and not text.startswith("<"):
            out.append(TranscriptMessage(role=role, text=text))
        return out

    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text" and block.get("text", "").strip():
                out.append(TranscriptMessage(role=role, text=block["text"].strip()))
            elif btype == "tool_use":
                out.append(
                    TranscriptMessage(
                        role="tool_use",
                        tool_name=block.get("name", "tool"),
                        tool_input=block.get("input", {}) or {},
                    )
                )
            elif btype == "tool_result":
                out.append(
                    TranscriptMessage(
                        role="tool_result",
                        text=_stringify_tool_result(block.get("content")),
                        is_error=bool(block.get("is_error")),
                    )
                )
    return out


def _stringify_tool_result(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return "" if content is None else str(content)
