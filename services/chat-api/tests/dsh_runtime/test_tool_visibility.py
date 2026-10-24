from __future__ import annotations

import asyncio

from app.dsh_runtime.model_gateway.tool_visibility import visible_tools


def test_automatic_mode_keeps_internal_url_collection_and_both_search_depths_visible() -> None:
    tools = [
        {"name": "knowledge_search"}, {"name": "web_collect"},
        {"name": "web_search"}, {"name": "progressive_research"},
    ]
    result = asyncio.run(visible_tools(tools, session_id="session-a", tenant_id="tenant-a"))
    assert [tool["name"] for tool in result or []] == [
        "knowledge_search", "web_collect", "web_search", "progressive_research",
    ]


def test_internal_knowledge_and_collector_are_visible_without_firecrawl_configuration() -> None:
    tools = [{"name": "knowledge_search"}, {"name": "web_collect"}]
    result = asyncio.run(visible_tools(tools, session_id="session-a", tenant_id="tenant-a"))
    assert [tool["name"] for tool in result or []] == ["knowledge_search", "web_collect"]


def test_named_learned_spreadsheet_question_cannot_run_script() -> None:
    tools = [{"name": "knowledge_search"}, {"name": "knowledge_read_document"}, {"name": "run_script"}, {"name": "web_search"}]
    result = asyncio.run(visible_tools(
        tools, session_id="session-a", tenant_id="tenant-a",
        messages=[{"role": "user", "content": "请根据已学习的《门店销售数据表.xlsx》，回答 GR0010218 的店名和三个月收入。"}],
    ))
    assert [tool["name"] for tool in result or []] == ["knowledge_search"]


def test_short_internal_knowledge_question_uses_search_only() -> None:
    tools = [{"name": "knowledge_search"}, {"name": "knowledge_read_document"}, {"name": "run_script"}]
    result = asyncio.run(visible_tools(
        tools, session_id="session-a", tenant_id="tenant-a",
        messages=[{"role": "user", "content": "仅基于内部知识：GR0010213 一到三月收入？"}],
    ))
    assert [tool["name"] for tool in result or []] == ["knowledge_search"]


def test_explicit_file_processing_keeps_script_available() -> None:
    tools = [{"name": "knowledge_search"}, {"name": "run_script"}]
    result = asyncio.run(visible_tools(
        tools, session_id="session-a", tenant_id="tenant-a",
        messages=[{"role": "user", "content": "请根据已上传的《门店销售数据表.xlsx》写脚本生成文件。"}],
    ))
    assert [tool["name"] for tool in result or []] == ["knowledge_search", "run_script"]


def test_named_pdf_with_spaces_still_limits_tools() -> None:
    tools = [{"name": "knowledge_search"}, {"name": "run_script"}]
    result = asyncio.run(visible_tools(
        tools, session_id="session-a", tenant_id="tenant-a",
        messages=[{"role": "user", "content": "请只根据企业知识文档《火山引擎AI 一体机核心介绍v1.0.pdf》回答综合性能提升多少？"}],
    ))
    assert [tool["name"] for tool in result or []] == ["knowledge_search"]


def test_explicit_full_document_read_keeps_read_tool() -> None:
    tools = [{"name": "knowledge_search"}, {"name": "knowledge_read_document"}, {"name": "run_script"}]
    result = asyncio.run(visible_tools(
        tools, session_id="session-a", tenant_id="tenant-a",
        messages=[{"role": "user", "content": "请通读《员工考勤及假期管理规定.pdf》全文，逐页总结职责。"}],
    ))
    assert [tool["name"] for tool in result or []] == ["knowledge_search", "knowledge_read_document"]
