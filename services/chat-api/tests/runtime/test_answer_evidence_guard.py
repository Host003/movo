from app.knowledge.agents.answer_evidence_guard import INSUFFICIENT, guard_absence_claim


def test_absence_claim_is_not_inferred_from_partial_retrieval():
    assert guard_absence_claim("文档没有综合性价比提升的表述。", ["TPS提升30%"] ) == INSUFFICIENT


def test_supported_positive_answer_survives():
    assert guard_absence_claim("综合性价比提升50%+。", ["综合性价比提升50%+"]) == "综合性价比提升50%+。"


def test_whole_document_absence_wording_is_also_blocked():
    assert guard_absence_claim("全文没有工装折损公式。", ["工装使用期限为三年"]) == INSUFFICIENT
