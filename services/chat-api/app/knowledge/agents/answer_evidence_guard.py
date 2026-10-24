"""Reject unsupported absence claims in knowledge answers."""

from __future__ import annotations

import re


INSUFFICIENT = "当前已检索片段不足以确认，不能据此判断原文不存在该信息。"
ABSENCE_CLAIM = re.compile(r"(?:文档|原文|资料|材料|全文|整份文件|整本文件).{0,20}(?:没有|不存在|未提及|未出现|无.{0,4}(?:表述|内容|信息))")


def guard_absence_claim(answer: str, cited_texts: list[str]) -> str:
    """A retrieved excerpt cannot prove absence from the entire document."""
    if ABSENCE_CLAIM.search(answer):
        return INSUFFICIENT
    if not cited_texts and answer.strip() and "未找到" not in answer and "不足" not in answer:
        return "内部知识库中未找到足够依据。"
    return answer
