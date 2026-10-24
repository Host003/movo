from __future__ import annotations

import re

from app.knowledge.api.schemas import KnowledgeChunk, KnowledgeQARequest, KnowledgeQAResult
from app.knowledge.citations.citation_resolver import parse_llm_json, resolve_citations
from app.knowledge.prompting.knowledge_qa_prompt import build_knowledge_qa_messages
from app.knowledge.agents.answer_evidence_guard import guard_absence_claim
from app.knowledge.agents.answer_fact_guard import INSUFFICIENT, guard_numeric_claims
from app.knowledge.agents.answer_support_guard import guard_supported_answer
from app.knowledge.retrieval.retrieval_client import knowledge_retrieval_client
from app.knowledge.retrieval.named_document import resolve_named_document
from app.services.llm import LLMService


_USED_CHUNK_IDS_RE = re.compile(
    r",?\s*[\"']?usedChunkIds[\"']?\s*:\s*\[[^\]]*]\s*}?\s*$",
    re.I | re.S,
)


def _clean_answer_text(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|markdown)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    text = _USED_CHUNK_IDS_RE.sub("", text).strip()
    text = re.sub(r"\s*}\s*$", "", text).strip()
    return text


def _extract_used_chunk_ids(raw: str) -> list[str]:
    text = str(raw or "")
    match = re.search(r"[\"']?usedChunkIds[\"']?\s*:\s*\[([^\]]*)]", text, flags=re.I | re.S)
    if not match:
        return []
    return re.findall(r"(?:[0-9a-f]{24,64}:)?chunk_[0-9A-Za-z_-]+", match.group(1), flags=re.I)


class KnowledgeQAAgent:
    async def retrieve_chunks(self, request: KnowledgeQARequest) -> list[KnowledgeChunk]:
        retrieval = await knowledge_retrieval_client.search(
            query=request.query,
            main_id=request.main_id,
            user_id=request.user_id,
            knowledge_base_ids=request.knowledge_base_ids,
            top_n=request.top_n,
            rerank=None,
        )
        return [
            KnowledgeChunk(
                document_id=item.documentId,
                chunk_id=item.chunkId,
                chunk_stage=item.chunkStage,
                text=item.text,
                contextual_text=item.contextualText,
                title_path=item.titlePath,
                page_no=item.pageNo,
                content_type=item.contentType,
                source_chunk_ids=item.sourceChunkIds,
                ordinal=item.ordinal,
                score=float(item.rerankScore if item.rerankScore is not None else item.score or 0),
                rerank_score=float(item.rerankScore) if item.rerankScore is not None else None,
                distance=item.distance,
                metadata=item.metadata,
            )
            for item in retrieval.items
            if item.text.strip() or item.contextualText.strip()
        ]

    async def answer_from_chunks(self, request: KnowledgeQARequest, chunks: list[KnowledgeChunk]) -> KnowledgeQAResult:
        if not chunks:
            return KnowledgeQAResult(
                answer="未在内部知识库中找到相关内容。",
                citations=[],
                retrieved_chunks=[],
                used_chunk_ids=[],
            )

        messages = build_knowledge_qa_messages(request.query, chunks)
        raw = await LLMService(intent="knowledge_qa").chat_complete(messages, temperature=None)
        parsed = parse_llm_json(raw)
        answer = _clean_answer_text(str(parsed.get("answer") or "")) or "内部知识库中未找到足够依据。"
        raw_used = parsed.get("usedChunkIds") or parsed.get("used_chunk_ids") or []
        if isinstance(raw_used, str):
            used_chunk_ids = [raw_used]
        elif isinstance(raw_used, list):
            used_chunk_ids = [str(item) for item in raw_used]
        else:
            used_chunk_ids = []
        if not used_chunk_ids:
            used_chunk_ids = _extract_used_chunk_ids(raw)
        citations = resolve_citations(chunks, used_chunk_ids)
        if not citations:
            answer = INSUFFICIENT
        else:
            answer = guard_absence_claim(answer, [item.text for item in citations])
        if citations and answer not in {
            "内部知识库中未找到足够依据。",
            "当前已检索片段不足以确认，不能据此判断原文不存在该信息。",
        }:
            answer = guard_supported_answer(
                answer, [item.text for item in citations], parsed.get("supportChecks"),
            )
        answer = guard_numeric_claims(answer, [
            "\n".join([item.text, str((item.metadata or {}).get("document_title") or "")])
            for item in citations
        ])
        return KnowledgeQAResult(
            answer=answer,
            citations=citations,
            retrieved_chunks=chunks,
            used_chunk_ids=[f"{item.document_id}:{item.chunk_id}" for item in citations],
            raw_model_output=raw,
        )

    async def answer(self, request: KnowledgeQARequest) -> KnowledgeQAResult:
        named = await resolve_named_document(request)
        if named is not None:
            if named.status != "ready":
                messages = {
                    "not_found": f"未找到当前用户可访问的指定知识文档《{named.filename}》。",
                    "ambiguous": f"存在多份同名知识文档《{named.filename}》，请指定目录或知识库。",
                    "parse_failed": f"指定知识文档《{named.filename}》已上传，但解析失败，当前无法据此回答。请在管理后台检查并重新学习。",
                    "index_failed": f"指定知识文档《{named.filename}》已解析，但学习索引失败，当前无法据此回答。请在管理后台检查并重新学习。",
                    "not_ready": f"指定知识文档《{named.filename}》尚未学习完成，当前无法据此回答。",
                    "empty": f"指定知识文档《{named.filename}》没有可用的知识片段，当前无法据此回答。",
                }
                return KnowledgeQAResult(answer=messages[named.status], document_status=named.status)
            return await self.answer_from_chunks(request, list(named.chunks))
        chunks = await self.retrieve_chunks(request)
        return await self.answer_from_chunks(request, chunks)


knowledge_qa_agent = KnowledgeQAAgent()
