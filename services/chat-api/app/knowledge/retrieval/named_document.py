"""Resolve an explicitly named knowledge file before semantic retrieval."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.db import get_db
from app.core.tenant import resolve_main_id
from app.knowledge.api.schemas import KnowledgeChunk, KnowledgeQARequest
from app.product.extensions import get_product_extension
from app.services.personal_knowledge.access import PersonalKnowledgeAccessService


_FILENAME = re.compile(r"([^\s《》“”'\"，,；;]+\.(?:pdf|docx|doc|xlsx|xls|pptx|ppt|csv|txt))\b", re.I)
_QUOTED_FILENAME = re.compile(r"《([^》]+\.(?:pdf|docx|doc|xlsx|xls|pptx|ppt|csv|txt))》", re.I)
_IDENTIFIER = re.compile(r"[A-Za-z]{1,8}\d{3,}|\d+(?:\.\d+)?%?")
_NOISE = re.compile(r"请只根据|企业内部知识文档|企业知识文档|企业知识库|请给出文档依据|回答|文档|文件|请问|是多少|是什么|有哪些|分别|多少")


@dataclass(frozen=True)
class NamedDocumentResult:
    filename: str
    status: str
    chunks: tuple[KnowledgeChunk, ...] = ()


def named_filename(query: str) -> str:
    match = _QUOTED_FILENAME.search(query) or _FILENAME.search(query)
    return match.group(1) if match else ""


async def resolve_named_document(request: KnowledgeQARequest) -> NamedDocumentResult | None:
    filename = named_filename(request.query)
    if not filename:
        return None
    tenant_id = resolve_main_id(request.main_id)
    db = get_db()
    cursor = db.knowledge_documents.find({
        "main_id": tenant_id, "original_filename": filename, "deleted_at": None,
    })
    accessible: list[dict[str, Any]] = []
    async for document in cursor:
        if not _in_selected_knowledge(document, request.knowledge_base_ids):
            continue
        if await _may_view(document, tenant_id=tenant_id, user_id=request.user_id):
            accessible.append(document)
            if len(accessible) > 1:
                return NamedDocumentResult(filename, "ambiguous")
    if not accessible:
        return NamedDocumentResult(filename, "not_found")

    document = accessible[0]
    if str(document.get("parse_status") or "") == "failed":
        return NamedDocumentResult(filename, "parse_failed")
    if str(document.get("index_status") or "") == "failed":
        return NamedDocumentResult(filename, "index_failed")
    if str(document.get("parse_status") or "") != "succeeded" or str(document.get("index_status") or "") != "succeeded":
        return NamedDocumentResult(filename, "not_ready")

    chunks = await _rank_document_chunks(
        db.knowledge_document_chunks,
        document=document,
        tenant_id=tenant_id,
        query=request.query,
        filename=filename,
        limit=request.top_n,
    )
    return NamedDocumentResult(filename, "ready" if chunks else "empty", tuple(chunks))


def _in_selected_knowledge(document: dict[str, Any], selected: list[str]) -> bool:
    if not selected:
        return True
    return bool({str(document.get("knowledge_base_id") or ""), str(document.get("resource_id") or "")} & set(selected))


async def _may_view(document: dict[str, Any], *, tenant_id: str, user_id: str) -> bool:
    if str(document.get("scope") or "organization") == "personal":
        resource_id = str(document.get("resource_id") or "")
        if not resource_id or not user_id:
            return False
        try:
            access = await PersonalKnowledgeAccessService().require_view(
                main_id=tenant_id, user_id=user_id, resource_id=resource_id,
            )
        except (LookupError, PermissionError):
            return False
        return str(access.resource.get("active_document_id") or "") == str(document.get("_id") or "")
    policy = get_product_extension().knowledge_access_policy
    if policy is not None:
        try:
            await policy.require_view(
                main_id=tenant_id, user_id=user_id, document_id=str(document.get("_id") or ""),
            )
        except (LookupError, PermissionError):
            return False
    return True


async def _rank_document_chunks(
    collection: Any, *, document: dict[str, Any], tenant_id: str,
    query: str, filename: str, limit: int,
) -> list[KnowledgeChunk]:
    document_id = str(document.get("_id") or "")
    scope = str(document.get("scope") or "organization")
    terms = _query_terms(query.replace(filename, ""))
    ranked: list[tuple[float, int, KnowledgeChunk]] = []
    cursor = collection.find({
        "main_id": tenant_id, "document_id": document_id, "chunk_stage": "rag",
    })
    async for row in cursor:
        text = str(row.get("contextual_text") or row.get("text") or "").strip()
        if not text:
            continue
        metadata = {
            **dict(row.get("metadata") or {}),
            "document_title": str(document.get("original_filename") or document.get("name") or ""),
            "knowledge_scope": scope,
            "knowledge_label": "个人知识" if scope == "personal" else "企业知识",
        }
        match_score = _match_score(terms, text)
        chunk = KnowledgeChunk(
            document_id=document_id, chunk_id=str(row.get("chunk_id") or ""),
            chunk_stage="rag", text=str(row.get("text") or ""),
            contextual_text=text, title_path=list(row.get("title_path") or []),
            page_no=row.get("page_no"), content_type=str(row.get("content_type") or "text"),
            source_chunk_ids=list(row.get("source_chunk_ids") or []),
            ordinal=int(row.get("ordinal") or 0), score=min(1.0, match_score), metadata=metadata,
        )
        ranked.append((match_score, -chunk.ordinal, chunk))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked[:max(1, limit)]]


def _query_terms(query: str) -> tuple[set[str], set[str]]:
    clean = _NOISE.sub("", query).lower()
    identifiers = set(_IDENTIFIER.findall(clean))
    chinese = "".join(re.findall(r"[\u3400-\u9fff]", clean))
    grams = {chinese[index:index + 2] for index in range(max(0, len(chinese) - 1))}
    return identifiers, grams


def _match_score(terms: tuple[set[str], set[str]], text: str) -> float:
    identifiers, grams = terms
    lowered = text.lower()
    clean = "".join(re.findall(r"[\u3400-\u9fff]", lowered))
    identifier_score = sum(
        (100 if len(term) >= 6 else 20 if len(term) >= 4 else 4)
        for term in identifiers
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", lowered)
    )
    gram_matches = sum(1 for gram in grams if gram in clean)
    return identifier_score + gram_matches / max(1, len(grams))


__all__ = ["NamedDocumentResult", "named_filename", "resolve_named_document"]
