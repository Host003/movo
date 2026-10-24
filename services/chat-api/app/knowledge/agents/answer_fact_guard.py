"""Enforce checkable numeric facts in a knowledge answer."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


_NUMBER = re.compile(r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?%?(?![A-Za-z0-9])")
_QUANTITY_UNIT = re.compile(
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>个工作日|工作日|万元|千元|公里|毫米|小时|分钟|个月|元|天|月|年|台|人|次|套|件)"
)
INSUFFICIENT = "内部知识库中未找到足够依据。"


def guard_numeric_claims(answer: str, cited_texts: list[str]) -> str:
    if not cited_texts:
        return answer
    source = "\n".join(cited_texts)
    answer = _QUANTITY_UNIT.sub(
        lambda match: match.group() if _has_cited_quantity(source, match.group("number"), match.group("unit"))
        else match.group("number"),
        answer,
    )
    source_numbers = [_numeric_value(match.group()) for match in _NUMBER.finditer(source)]
    prose = re.sub(r"(?m)^\s*\d+[.)、]\s+", "", answer)
    for match in _NUMBER.finditer(prose):
        value = _numeric_value(match.group())
        if value is None or not any(_matches(value, candidate) for candidate in source_numbers if candidate is not None):
            return INSUFFICIENT
    return answer


def _has_cited_quantity(source: str, raw_number: str, unit: str) -> bool:
    claimed = _numeric_value(raw_number)
    if claimed is None:
        return False
    for match in _QUANTITY_UNIT.finditer(source):
        source_value = _numeric_value(match.group("number"))
        if match.group("unit") == unit and source_value is not None and _matches(claimed, source_value):
            return True
    return False


def _numeric_value(raw: str) -> tuple[Decimal, bool] | None:
    try:
        return Decimal(raw.rstrip("%").replace(",", "")), raw.endswith("%")
    except InvalidOperation:
        return None


def _matches(claim: tuple[Decimal, bool], source: tuple[Decimal, bool]) -> bool:
    if claim[1] != source[1]:
        return False
    if claim[0] == source[0]:
        return True
    return source[0].quantize(Decimal("0.01")) == claim[0] and claim[0].as_tuple().exponent >= -2
