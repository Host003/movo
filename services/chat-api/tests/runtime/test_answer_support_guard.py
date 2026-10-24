from app.knowledge.agents.answer_fact_guard import INSUFFICIENT
from app.knowledge.agents.answer_support_guard import guard_supported_answer


def test_unsupported_advice_is_removed_while_supported_answer_remains():
    source = "公司每年 3 月、9 月集中申请工装。非标准工装另行呈批。"
    answer = "每年 3 月、9 月集中申请。\n如果错过 9 月，建议按非标准情形呈批。"
    checks = [
        {"statement": "每年 3 月、9 月集中申请。", "supported": True, "evidence": "每年 3 月、9 月集中申请工装"},
        {"statement": "如果错过 9 月，建议按非标准情形呈批。", "supported": False, "evidence": ""},
    ]
    assert guard_supported_answer(answer, [source], checks) == "每年 3 月、9 月集中申请。"


def test_model_cannot_invent_evidence_or_new_answer_text():
    answer = "按月汇总并抽查。\n每月移交工资核算。"
    checks = [
        {"statement": "按月汇总并抽查。", "supported": True, "evidence": "按月汇总公司考勤记录并抽查"},
        {"statement": "每月移交工资核算。", "supported": True, "evidence": "每月移交工资核算"},
        {"statement": "额外编造的句子。", "supported": True, "evidence": "按月汇总公司考勤记录并抽查"},
    ]
    assert guard_supported_answer(answer, ["人力资源部负责按月汇总公司考勤记录并抽查。"], checks) == "按月汇总并抽查。"


def test_missing_checks_fail_closed():
    assert guard_supported_answer("未经核验的建议。", ["其他内容"], None) == INSUFFICIENT


def test_numeric_claim_must_match_its_own_evidence_excerpt():
    answer = "期限是 3 天。"
    checks = [{"statement": answer, "supported": True, "evidence": "期限是 5 天"}]
    assert guard_supported_answer(answer, ["期限是 5 天，其他事项是 3 天。"], checks) == INSUFFICIENT


def test_table_scaffold_survives_when_supported_rows_are_kept():
    answer = "| 月份 | 收入 |\n| --- | --- |\n| 一月 | 17017 |\n| 二月 | 99999 |"
    checks = [
        {"statement": "| 一月 | 17017 |", "supported": True, "evidence": "一月收入：17017"},
        {"statement": "| 二月 | 99999 |", "supported": False, "evidence": ""},
    ]
    assert guard_supported_answer(answer, ["一月收入：17017"], checks) == (
        "| 月份 | 收入 |\n| --- | --- |\n| 一月 | 17017 |"
    )
