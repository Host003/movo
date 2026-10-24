from __future__ import annotations

import json
from datetime import datetime, timezone

from app.dsh_runtime.contracts import KernelEventEnvelope, KernelEventSource
from app.dsh_runtime.events.knowledge_final_guard import KnowledgeFinalGuard
from app.dsh_runtime.events.projection import KernelEventProjector
from app.knowledge.agents.answer_evidence_guard import INSUFFICIENT


def _event(cursor: int, kind: str, payload: dict) -> KernelEventEnvelope:
    return KernelEventEnvelope(
        event_id=f"event-{cursor}", runtime_id="runtime", session_id="session",
        profile_version="profile", cursor=cursor, type=kind,
        occurred_at=datetime.now(timezone.utc), payload=payload,
        source=KernelEventSource(kernel_version="test", native_event_type=kind),
    )


def _project(guard: KnowledgeFinalGuard, projector: KernelEventProjector, event: KernelEventEnvelope):
    return guard.apply(event, projector.project(event, message_id="message"))


def _search(projector: KernelEventProjector, guard: KnowledgeFinalGuard, *, cursor: int, call_id: str, answer: str, document_status: str = ""):
    started = _event(cursor, "tool.call.started", {
        "callId": call_id, "name": "knowledge_search",
        "arguments": json.dumps({"query": "《门店销售数据表.xlsx》GR0010218 的店名"}),
    })
    _project(guard, projector, started)
    completed = _event(cursor + 1, "tool.call.completed", {"message": {
        "source": {"callId": call_id},
        "content": [{"type": "tool-result", "toolCallId": call_id, "isError": False,
                     "content": [{"type": "text", "text": json.dumps({
                         "success": True, "provider": "internal_knowledge_qa", "answer": answer,
                         "documentStatus": document_status,
                     })}]}],
    }})
    _project(guard, projector, completed)


def _final(text: str, cursor: int = 10) -> KernelEventEnvelope:
    return _event(cursor, "agent.message.completed", {
        "message": {"content": [{"type": "text", "text": text}]},
    })


def test_single_named_search_uses_grounded_tool_answer_verbatim() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("请根据《门店销售数据表.xlsx》回答店名")
    _search(projector, guard, cursor=1, call_id="search-1", answer="安徽安庆华茂店。")
    projected = _project(guard, projector, _final("安徽安庆华茂店，位于繁华商圈。"))
    assert projected["payload"]["text"] == "安徽安庆华茂店。"
    assert projected["payload"]["source"] == "knowledge_tool_answer"


def test_multiple_searches_cannot_claim_absence_from_partial_evidence() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("请根据《工装挂历制度.pdf》回答")
    _search(projector, guard, cursor=1, call_id="search-1", answer="依据不足。")
    _search(projector, guard, cursor=3, call_id="search-2", answer="依据不足。")
    projected = _project(guard, projector, _final("文档全文没有实习期申领规定。"))
    assert projected["payload"]["text"] == INSUFFICIENT


def test_multiple_grounded_searches_are_combined_without_outer_additions() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("请根据《工装挂历制度.pdf》回答申领月份和处罚金额")
    _search(projector, guard, cursor=1, call_id="search-1", answer="每年 3 月、9 月申请。")
    _search(projector, guard, cursor=3, call_id="search-2", answer="未按通知着装处罚 100 元/次。")
    projected = _project(guard, projector, _final("3 月申请，处罚 100 元，还要缴纳保证金。"))
    assert projected["payload"]["text"] == "每年 3 月、9 月申请。\n\n未按通知着装处罚 100 元/次。"


def test_multiple_searches_do_not_repeat_near_identical_grounded_rows() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("仅基于内部知识：一到三月收入各是多少？")
    first = "| 月份 | 收入 |\n| --- | --- |\n| 一月 | 17017.76 |\n| 二月 | 13456 |"
    second = "| 月份 | 收入 |\n| --- | --- |\n| 一月 | 17,017.76 |\n| 三月 | 14567 |"
    _search(projector, guard, cursor=1, call_id="search-1", answer=first)
    _search(projector, guard, cursor=3, call_id="search-2", answer=second)
    text = _project(guard, projector, _final("重复表格"))["payload"]["text"]
    assert text.count("| 月份 | 收入 |") == 1
    assert text.count("| --- | --- |") == 1
    assert text.count("| 一月 |") == 1
    assert "| 二月 | 13456 |" in text
    assert "| 三月 | 14567 |" in text


def test_similar_statements_with_different_numbers_remain_distinct() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("仅基于内部知识：A、B 模式几天开票？")
    _search(projector, guard, cursor=1, call_id="search-1", answer="A 模式收到确认单后 5 个工作日内开票。")
    _search(projector, guard, cursor=3, call_id="search-2", answer="B 模式收到确认单后 3 个工作日内开票。")
    text = _project(guard, projector, _final("结算说明"))["payload"]["text"]
    assert "A 模式收到确认单后 5 个工作日内开票。" in text
    assert "B 模式收到确认单后 3 个工作日内开票。" in text


def test_similar_statements_with_opposite_meaning_remain_distinct() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("仅基于内部知识：是否可以延期？")
    _search(projector, guard, cursor=1, call_id="search-1", answer="满足条件后可以申请延期。")
    _search(projector, guard, cursor=3, call_id="search-2", answer="未满足条件时不可以申请延期。")
    text = _project(guard, projector, _final("申请规则"))["payload"]["text"]
    assert "满足条件后可以申请延期。" in text
    assert "未满足条件时不可以申请延期。" in text


def test_unrelated_conversation_keeps_model_synthesis() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("请介绍天气")
    projected = _project(guard, projector, _final("今天可能下雨。"))
    assert projected["payload"]["text"] == "今天可能下雨。"


def test_short_internal_knowledge_question_rejects_outer_calculation() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("仅基于内部知识：综合性价比提升多少？")
    _search(projector, guard, cursor=1, call_id="search-1", answer="内部知识库中未找到足够依据。")
    projected = _project(guard, projector, _final("综合性价比约提升 86%。"))
    assert projected["payload"]["text"] == INSUFFICIENT


def test_named_document_answer_without_any_evidence_is_blocked() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("《门店销售数据表.xlsx》里 GR0010218 的店名？")
    projected = _project(guard, projector, _final("这家店叫北京店。"))
    assert projected["payload"]["text"] == "未取得指定知识文档的可核验依据，暂不能回答。"


def test_failed_learning_status_survives_multiple_searches() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("《北交所上市企业列表.xlsx》有多少家企业？")
    status = "指定文档已上传，但解析失败。"
    _search(projector, guard, cursor=1, call_id="search-1", answer=status, document_status="parse_failed")
    _search(projector, guard, cursor=3, call_id="search-2", answer="未找到依据。")
    projected = _project(guard, projector, _final("这个文件没有上传，请重新上传。"))
    assert projected["payload"]["text"] == status


def test_mixed_tool_task_keeps_its_final_synthesis() -> None:
    projector = KernelEventProjector()
    guard = KnowledgeFinalGuard("根据《项目资料.pdf》生成报告")
    _search(projector, guard, cursor=1, call_id="search-1", answer="已找到项目资料。", document_status="not_ready")
    _project(guard, projector, _event(3, "tool.call.started", {
        "callId": "file-1", "name": "create_file", "arguments": "{}",
    }))
    projected = _project(guard, projector, _final("报告已生成。"))
    assert projected["payload"]["text"] == "报告已生成。"
