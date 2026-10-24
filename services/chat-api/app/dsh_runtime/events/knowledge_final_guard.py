"""Keep named-document answers within the evidence returned by knowledge tools."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.dsh_runtime.contracts import KernelEventEnvelope
from app.dsh_runtime.events.projection import KernelEventProjector
from app.knowledge.agents.answer_evidence_guard import ABSENCE_CLAIM, INSUFFICIENT
from app.knowledge.retrieval.named_document import named_filename
from app.dsh_runtime.model_gateway.tool_visibility import _KNOWLEDGE_ONLY_CUE


class KnowledgeFinalGuard:
    def __init__(self, question: str = "") -> None:
        self._named = bool(named_filename(question))
        self._knowledge_only = bool(_KNOWLEDGE_ONLY_CUE.search(question))
        self._answers: list[str] = []
        self._other_tool = False
        self._document_evidence = False
        self._status_answer = ""

    def apply(
        self, event: KernelEventEnvelope, projected: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if projected is None:
            return None
        if event.type == "tool.call.started":
            name = str((projected.get("payload") or {}).get("name") or "")
            if name and name != "knowledge_search":
                self._other_tool = True
        elif event.type == "tool.call.completed":
            self._capture(event, projected)

        if projected.get("item_kind") != "final_answer":
            return projected
        authoritative = (self._named or self._knowledge_only) and bool(self._answers) and not self._other_tool
        status_authoritative = (self._named or self._knowledge_only) and bool(self._status_answer) and not self._other_tool
        if projected.get("type") == "item.delta" and (authoritative or status_authoritative):
            return None
        if projected.get("type") != "item.completed":
            return projected
        text = str((projected.get("payload") or {}).get("text") or "")
        if status_authoritative:
            return _replace_text(projected, self._status_answer, "knowledge_document_status")
        if authoritative:
            return _replace_text(projected, self._grounded_answer(), "knowledge_tool_answer")
        if (self._named or self._knowledge_only) and not self._other_tool and ABSENCE_CLAIM.search(text):
            return _replace_text(projected, INSUFFICIENT, "knowledge_evidence_guard")
        if (self._named or self._knowledge_only) and not self._other_tool and not self._answers and not self._document_evidence:
            return _replace_text(projected, "未取得指定知识文档的可核验依据，暂不能回答。", "knowledge_evidence_guard")
        return projected

    def _capture(self, event: KernelEventEnvelope, projected: dict[str, Any]) -> None:
        payload = projected.get("payload") or {}
        if payload.get("name") == "knowledge_read_document" and payload.get("ok"):
            evidence = payload.get("evidence_bundle") or {}
            self._document_evidence = bool(evidence.get("sources"))
        if payload.get("name") != "knowledge_search" or not payload.get("ok"):
            return
        query = str((payload.get("args") or {}).get("query") or "")
        self._named = self._named or bool(named_filename(query))
        _, _, _, result = KernelEventProjector._tool_result(event.payload)
        if not isinstance(result, dict) or result.get("provider") != "internal_knowledge_qa":
            return
        answer = str(result.get("answer") or "").strip()
        if result.get("documentStatus") in {"parse_failed", "index_failed", "not_ready", "empty", "not_found", "ambiguous"}:
            self._status_answer = answer
        if answer:
            self._answers.append(answer)

    def _grounded_answer(self) -> str:
        distinct = list(dict.fromkeys(self._answers))
        supported = [
            answer for answer in distinct
            if not any(marker in answer for marker in ("依据不足", "未找到足够依据", "无法据此回答", "不能据此判断原文不存在"))
        ]
        return "\n\n".join(supported) if supported else INSUFFICIENT


def _replace_text(projected: dict[str, Any], text: str, source: str) -> dict[str, Any]:
    result = deepcopy(projected)
    result["payload"] = {
        **dict(result.get("payload") or {}),
        "text": text,
        "provisional": False,
        "source": source,
    }
    return result


__all__ = ["KnowledgeFinalGuard"]
