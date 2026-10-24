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
