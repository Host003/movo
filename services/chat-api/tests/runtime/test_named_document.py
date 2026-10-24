from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.knowledge.api.schemas import KnowledgeQARequest
from app.knowledge.retrieval import named_document
from app.knowledge.agents import knowledge_qa_agent as qa_module


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def __aiter__(self):
        async def iterate():
            for row in self.rows:
                yield row
        return iterate()


class _Collection:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query):
        return _Cursor([
            row for row in self.rows
            if all(row.get(key) == value for key, value in query.items())
        ])


def _db(*, documents, chunks=()):
    return SimpleNamespace(
        knowledge_documents=_Collection(documents),
        knowledge_document_chunks=_Collection(chunks),
    )


def _request(query):
    return KnowledgeQARequest(query=query, main_id="tenant", user_id="user", top_n=2)


def test_filename_with_spaces_is_extracted() -> None:
    assert named_document.named_filename("请根据《火山引擎AI 一体机核心介绍v1.0.pdf》回答") == "火山引擎AI 一体机核心介绍v1.0.pdf"


def test_identifier_ranking_requires_complete_token() -> None:
    terms = named_document._query_terms("PX2024001 的项目负责人是谁？")
    assert named_document._match_score(terms, "项目 PX2024001 的负责人：王工") > named_document._match_score(
        terms, "项目 PX20240010 的负责人：李工"
    )


def test_failed_learning_is_reported_as_file_status(monkeypatch) -> None:
    monkeypatch.setattr(named_document, "get_db", lambda: _db(documents=[{
        "_id": "failed", "main_id": "tenant", "original_filename": "北交所上市企业列表.xlsx",
        "scope": "organization", "deleted_at": None, "parse_status": "failed",
    }]))
    monkeypatch.setattr(named_document, "get_product_extension", lambda: SimpleNamespace(knowledge_access_policy=None))
    result = asyncio.run(named_document.resolve_named_document(_request("《北交所上市企业列表.xlsx》有多少家企业？")))
    assert result is not None and result.status == "parse_failed"


def test_named_file_ranks_its_own_exact_row_without_other_documents(monkeypatch) -> None:
    documents = [{
        "_id": "stores", "main_id": "tenant", "original_filename": "门店销售数据表.xlsx",
        "scope": "organization", "deleted_at": None,
        "parse_status": "succeeded", "index_status": "succeeded",
    }]
    chunks = [
        {"main_id": "tenant", "document_id": "stores", "chunk_stage": "rag", "chunk_id": "chunk_1", "ordinal": 0, "text": "店铺编码：GR0010218；店铺名称：安徽安庆华茂店"},
        {"main_id": "tenant", "document_id": "stores", "chunk_stage": "rag", "chunk_id": "chunk_2", "ordinal": 1, "text": "店铺编码：GR0010220；店铺名称：安徽安庆中心店"},
        {"main_id": "tenant", "document_id": "other", "chunk_stage": "rag", "chunk_id": "chunk_3", "ordinal": 0, "text": "GR0010220 错误店名"},
    ]
    monkeypatch.setattr(named_document, "get_db", lambda: _db(documents=documents, chunks=chunks))
    monkeypatch.setattr(named_document, "get_product_extension", lambda: SimpleNamespace(knowledge_access_policy=None))
    result = asyncio.run(named_document.resolve_named_document(_request("《门店销售数据表.xlsx》中 GR0010220 的店名是什么？")))
    assert result is not None and result.status == "ready"
    assert result.chunks[0].chunk_id == "chunk_2"
    assert all(chunk.document_id == "stores" for chunk in result.chunks)
    assert result.chunks[0].metadata["document_title"] == "门店销售数据表.xlsx"


def test_access_denied_is_indistinguishable_from_missing(monkeypatch) -> None:
    monkeypatch.setattr(named_document, "get_db", lambda: _db(documents=[{
        "_id": "private", "main_id": "tenant", "original_filename": "员工资料.pdf",
        "scope": "organization", "deleted_at": None,
    }]))

    class _Deny:
        async def require_view(self, **_kwargs):
            raise PermissionError("forbidden")

    monkeypatch.setattr(named_document, "get_product_extension", lambda: SimpleNamespace(knowledge_access_policy=_Deny()))
    result = asyncio.run(named_document.resolve_named_document(_request("《员工资料.pdf》里写了什么？")))
    assert result is not None and result.status == "not_found"


def test_agent_reports_failed_document_instead_of_attachment_message(monkeypatch) -> None:
    async def failed(_request):
        return named_document.NamedDocumentResult("北交所上市企业列表.xlsx", "parse_failed")

    monkeypatch.setattr(qa_module, "resolve_named_document", failed)
    result = asyncio.run(qa_module.KnowledgeQAAgent().answer(_request("《北交所上市企业列表.xlsx》有多少家企业？")))
    assert "已上传，但解析失败" in result.answer
    assert result.document_status == "parse_failed"
    assert not result.citations


@pytest.mark.parametrize("filename,question,expected_page", [
    ("员工考勤及假期管理规定.pdf", "人力资源部对公司考勤记录有哪些按月职责？", 1),
    ("工装挂历制度.pdf", "实习期间的员工可以申领工装吗？", 2),
    ("工装挂历制度.pdf", "领用工装 10 个月后离职折损率是多少？", 2),
    ("火山引擎AI 一体机核心介绍v1.0.pdf", "Serving Kit 综合性能提升多少？", 3),
])
def test_real_regression_question_ranks_correct_page(filename, question, expected_page) -> None:
    from pypdf import PdfReader

    path = Path("/Users/jack/Downloads/测试文档") / filename
    if not path.exists():
        pytest.skip("local QA document unavailable")
    scores = [
        named_document._match_score(named_document._query_terms(question), page.extract_text() or "")
        for page in PdfReader(str(path)).pages
    ]
    assert max(range(len(scores)), key=scores.__getitem__) + 1 == expected_page
