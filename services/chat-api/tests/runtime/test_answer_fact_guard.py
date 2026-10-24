from app.knowledge.agents.answer_fact_guard import INSUFFICIENT, guard_numeric_claims


def test_unquoted_derived_percentage_is_rejected():
    assert guard_numeric_claims("综合性价比提升约 86%。", ["TPS 提升 30%，TCO 降低 30%"] ) == INSUFFICIENT


def test_cited_percentage_survives():
    assert guard_numeric_claims("综合性价比提升 50%+。", ["综合性价比提升 50%+"]) == "综合性价比提升 50%+。"


def test_rounded_spreadsheet_value_is_allowed():
    assert guard_numeric_claims("一月收入 17,017.76。", ["一月收入 17017.7619047619"]) == "一月收入 17,017.76。"


def test_unsupported_quantity_unit_is_removed_generically():
    assert guard_numeric_claims("一月收入 17017 元。", ["一月收入 17017"]) == "一月收入 17017。"
    assert guard_numeric_claims("设备可 1 台起步。", ["设备可 1 台起步"]) == "设备可 1 台起步。"


def test_unit_must_belong_to_same_cited_number():
    assert guard_numeric_claims("收入 17017 元。", ["收入 17017；另有支出 300 元"]) == "收入 17017。"


def test_equivalent_unicode_number_forms_share_evidence_without_rewriting_answer():
    source = "デフォルトは25％、最小は10％、最大は30％。"
    answer = "默认 25%，最小 10%，最大 30%。"
    assert guard_numeric_claims(answer, [source]) == answer
    assert guard_numeric_claims("增长 １，０００．５％。", ["增长 1,000.5%。"]) == "增长 １，０００．５％。"


def test_unicode_normalization_does_not_approve_different_values():
    assert guard_numeric_claims("默认 35%。", ["デフォルトは25％。"] ) == INSUFFICIENT
    assert guard_numeric_claims("下降 −25%。", ["增长 25%。"] ) == INSUFFICIENT
    assert guard_numeric_claims("下降 -25%。", ["下降 −25％。"] ) == "下降 -25%。"
