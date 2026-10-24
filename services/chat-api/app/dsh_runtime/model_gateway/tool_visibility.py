"""Per-turn visibility for immutable Runtime Profile tools."""

from __future__ import annotations

import re
from typing import Any

from app.knowledge.retrieval.named_document import named_filename

_KNOWLEDGE_CUE = re.compile(r"知识库|企业知识|已上传|已学习|文档中|文件中|只根据|根据《|通读|逐页")
_FILE_ACTION = re.compile(r"运行脚本|写脚本|执行代码|生成文件|导出文件|修改文件|上传文件|上传文档|下载文件|处理附件|上传附件")
_FULL_READ_CUE = re.compile(r"通读|逐页|阅读全文|全文阅读|完整阅读|全文总结|整份文档总结")
_KNOWLEDGE_ONLY_CUE = re.compile(r"仅基于内部知识|只基于内部知识|只根据内部知识|仅根据内部知识|只查内部知识|仅查内部知识")


def _latest_user_text(messages: list[dict[str, Any]] | None) -> str:
    for message in reversed(messages or []):
        if message.get("role") != "user":
            continue
        content = message.get("content") or ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_blocks = [str(block.get("text") or "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
            if text_blocks:
                return "\n".join(text_blocks)
    return ""


def _is_knowledge_document_question(messages: list[dict[str, Any]] | None) -> bool:
    text = _latest_user_text(messages)
    return bool(
        not _FILE_ACTION.search(text)
        and (_KNOWLEDGE_ONLY_CUE.search(text) or (named_filename(text) and _KNOWLEDGE_CUE.search(text)))
    )

async def visible_tools(
    tools: list[dict[str, Any]] | None,
    *,
    session_id: str,
    tenant_id: str,
    messages: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]] | None:
    """Hide tools that are unavailable in the active trusted turn.

    Runtime Profiles remain immutable. Internal knowledge search is available
    in automatic and strict retrieval modes; ASKAI still injects its governed
    tenant and knowledge-base scope when the tool executes. URL collection is
    always available through direct HTTP; Firecrawl is only an optional fallback.
    """
    if not tools:
        return tools
    del session_id, tenant_id
    if _is_knowledge_document_question(messages):
        names = {"knowledge_search"}
        if _FULL_READ_CUE.search(_latest_user_text(messages)):
            names.add("knowledge_read_document")
        knowledge_tools = [tool for tool in tools if tool.get("name") in names]
        if knowledge_tools:
            return knowledge_tools
    return list(tools)


__all__ = ["visible_tools"]
