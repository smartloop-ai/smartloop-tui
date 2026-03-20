"""tui/events.py — SSE event dataclasses and stream parsers."""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx


# ---------------------------------------------------------------------------
# Chat SSE events
# ---------------------------------------------------------------------------

@dataclass
class SSEStatus:
    """A processing-status event from the server."""
    step: str
    status: str
    message: str


@dataclass
class SSEContent:
    """A content-token event (one chunk of the assistant reply)."""
    text: str


@dataclass
class SSEUsage:
    """Token usage info returned after streaming completes."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    max_context_tokens: int


@dataclass
class SSEDone:
    """Signals end of the SSE stream."""


SSEEvent = SSEStatus | SSEContent | SSEUsage | SSEDone


# ---------------------------------------------------------------------------
# Bootstrap SSE events
# ---------------------------------------------------------------------------

@dataclass
class BootstrapProgress:
    """Download progress event with byte counts."""
    filename: str
    downloaded: int
    total: int


@dataclass
class BootstrapStatus:
    """A status update from bootstrap (checking, loading, etc.)."""
    status: str
    message: str


@dataclass
class BootstrapComplete:
    """Bootstrap completed — carries model name and project info."""
    model_name: str
    project: dict | None


@dataclass
class BootstrapError:
    """Bootstrap failed."""
    message: str


BootstrapEvent = BootstrapProgress | BootstrapStatus | BootstrapComplete | BootstrapError


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

async def parse_bootstrap_sse(response: httpx.Response):
    """Async generator that yields typed events from a bootstrap SSE stream.

    Bootstrap SSE uses ``event: <type>\\ndata: <json>\\n\\n`` format.
    """
    current_event_type: str | None = None
    async for raw_line in response.aiter_lines():
        if raw_line.startswith("event: "):
            current_event_type = raw_line[7:].strip()
            continue
        if not raw_line.startswith("data: "):
            if raw_line.strip() == "":
                current_event_type = None
            continue
        try:
            data = json.loads(raw_line[6:])
        except json.JSONDecodeError:
            continue

        event_type = current_event_type or "progress"

        if event_type == "error":
            yield BootstrapError(message=data.get("message", "Unknown error"))
        elif event_type == "complete":
            yield BootstrapComplete(
                model_name=data.get("model_name", ""),
                project=data.get("project"),
            )
        elif "downloaded" in data and "total" in data:
            yield BootstrapProgress(
                filename=data.get("filename", ""),
                downloaded=data["downloaded"],
                total=data["total"],
            )
        else:
            yield BootstrapStatus(
                status=data.get("status", ""),
                message=data.get("message", ""),
            )

        current_event_type = None


async def parse_sse_stream(response: httpx.Response):
    """Async generator that yields typed SSE events from a streaming response."""
    async for raw_line in response.aiter_lines():
        if not raw_line.startswith("data: "):
            continue
        data = raw_line[6:]
        if data == "[DONE]":
            yield SSEDone()
            return
        try:
            chunk = json.loads(data)
        except json.JSONDecodeError:
            continue

        if chunk.get("object") == "chat.status":
            yield SSEStatus(
                step=chunk.get("step", ""),
                status=chunk.get("status", ""),
                message=chunk.get("message", ""),
            )
        elif chunk.get("object") == "chat.usage":
            yield SSEUsage(
                prompt_tokens=chunk.get("prompt_tokens", 0),
                completion_tokens=chunk.get("completion_tokens", 0),
                total_tokens=chunk.get("total_tokens", 0),
                max_context_tokens=chunk.get("max_context_tokens", 0),
            )
        elif chunk.get("choices") and chunk["choices"][0].get("delta"):
            content = chunk["choices"][0]["delta"].get("content", "")
            if content:
                yield SSEContent(text=content)
