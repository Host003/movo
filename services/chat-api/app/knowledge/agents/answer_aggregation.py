"""Combine grounded search answers without repeating the same statement."""

from __future__ import annotations

import re
import unicodedata


def merge_grounded_answers(answers: list[str]) -> str:
    kept: list[str] = []
    keys: list[str] = []
    for answer in answers:
        block: list[str] = []
        for line in str(answer or "").splitlines():
            line = line.strip()
            if not line or _is_decorative(line):
                continue
            key = _statement_key(line)
            if not key or any(_same_statement(key, previous) for previous in keys):
                continue
            keys.append(key)
            block.append(line)
        if block:
            if kept and not (_is_table_row(kept[-1]) and _is_table_row(block[0])):
                kept.append("")
            kept.extend(block)
    return "\n".join(kept)


def _is_decorative(line: str) -> bool:
    return bool(re.fullmatch(r"[-\s]+", line))


def _is_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|")


def _statement_key(line: str) -> str:
    if re.fullmatch(r"\|(?:\s*:?-{3,}:?\s*\|)+", line):
        return f"table-divider-{line.count('|') - 1}"
    normalized = unicodedata.normalize("NFKC", line).lower()
    normalized = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)、]\s+|#{1,6}\s+)", "", normalized)
    return "".join(char for char in normalized if char.isalnum())


def _same_statement(left: str, right: str) -> bool:
    return left == right


__all__ = ["merge_grounded_answers"]
