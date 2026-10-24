"""Validate answer statements against exact excerpts from cited knowledge."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.knowledge.agents.answer_fact_guard import INSUFFICIENT, guard_numeric_claims


_SENTENCE_END = re.compile(r"(?<=[。！？；])|(?<=\.)\s+(?=[A-Z])")
_TABLE_DIVIDER = re.compile(r"\|(?:\s*:?-{3,}:?\s*\|)+")
_SPACE = re.compile(r"\s+")


def _statements(answer: str) -> list[str]:
    return [part.strip() for line in answer.splitlines() for part in _SENTENCE_END.split(line) if part.strip()]


def _normalized(text: str) -> str:
    return _SPACE.sub("", unicodedata.normalize("NFKC", text)).casefold()


def guard_supported_answer(answer: str, cited_texts: list[str], checks: Any) -> str:
    """Retain only original answer text with a verified source excerpt.

    The answering model supplies checks in the same completion, so validation
    does not add a second model request or another failure dependency.
    """
    statements = _statements(answer)
    if not statements or not cited_texts or not isinstance(checks, list):
        return INSUFFICIENT
    normalized_source = _normalized("\n\n".join(cited_texts))
    approved: set[str] = set()
    for check in checks:
        if not isinstance(check, dict) or check.get("supported") is not True:
            continue
        statement = _normalized(str(check.get("statement") or ""))
        excerpt = _normalized(str(check.get("evidence") or ""))
        if (statement and len(excerpt) >= 4 and excerpt in normalized_source
                and guard_numeric_claims(str(check["statement"]), [str(check["evidence"])])
                == str(check["statement"])):
            approved.add(statement)
    accepted = {index for index, statement in enumerate(statements) if _normalized(statement) in approved}
    for index, statement in enumerate(statements):
        if not _TABLE_DIVIDER.fullmatch(statement) or index == 0 or not _is_table_row(statements[index - 1]):
            continue
        following = index + 1
        while following < len(statements) and _is_table_row(statements[following]):
            if following in accepted:
                accepted.update({index - 1, index})
                break
            following += 1
    kept = [statement for index, statement in enumerate(statements) if index in accepted]
    return "\n".join(kept) if kept else INSUFFICIENT


def _is_table_row(statement: str) -> bool:
    return statement.startswith("|") and statement.endswith("|")


__all__ = ["guard_supported_answer"]
