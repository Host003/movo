"""Stable identifiers used for exact knowledge lookups."""

from __future__ import annotations

import re


IDENTIFIER = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{1,12}[A-Za-z0-9-]*\d{4,}[A-Za-z0-9-]*(?![A-Za-z0-9])")


def extract_identifiers(text: str) -> list[str]:
    return list(dict.fromkeys(match.group().upper() for match in IDENTIFIER.finditer(text)))
