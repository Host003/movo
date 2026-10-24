"""Preserve the user's named file when the model forms a knowledge query."""

from __future__ import annotations

import json
from typing import Any

from app.knowledge.retrieval.named_document import named_filename

from .tool_visibility import _latest_user_text


def scope_knowledge_tool_arguments(
    *, name: str, arguments: str, messages: list[dict[str, Any]],
) -> str:
    if name != "knowledge_search":
        return arguments
    filename = named_filename(_latest_user_text(messages))
    if not filename:
        return arguments
    try:
        payload = json.loads(arguments)
    except (TypeError, ValueError):
        return arguments
    if not isinstance(payload, dict):
        return arguments
    query = str(payload.get("query") or "").strip()
    if not query:
        return arguments
    if named_filename(query) == filename:
        return arguments
    payload["query"] = f"《{filename}》 {query}"
    return json.dumps(payload, ensure_ascii=False)


__all__ = ["scope_knowledge_tool_arguments"]
