"""Compare PDF native text with Docling output and recover dropped pages."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any


MIN_NATIVE_CHARS = 80
MIN_COVERAGE = 0.65
MIN_MISSING_CHARS = 16
_CRITICAL_VALUE = re.compile(r"\d+(?:\.\d+)?\s*%|[A-Za-z]{1,8}\d{4,}")


def supplement_pdf_chunks(path: Path, chunks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from pypdf import PdfReader

    pages = PdfReader(str(path)).pages
    report: list[dict[str, Any]] = []
    for page_no, page in enumerate(pages, start=1):
        try:
            native_text = (page.extract_text() or "").strip()
        except Exception:
            native_text = ""
        native_chars = _characters(native_text)
        page_chunks = [item for item in chunks if item.get("pageNo") == page_no]
        parsed_text = "\n".join(str(item.get("text") or "") for item in page_chunks)
        coverage = _coverage(native_chars, _characters(parsed_text))
        missing_lines = _missing_lines(native_text, parsed_text) if len(native_chars) >= MIN_NATIVE_CHARS else []
        missing_chars = sum(_characters(line).total() for line in missing_lines)
        recovered = bool(missing_lines) and (
            coverage < MIN_COVERAGE or missing_chars >= MIN_MISSING_CHARS
            or any(_CRITICAL_VALUE.search(line) for line in missing_lines)
        )
        if recovered:
            ordinal = len(chunks)
            recovery_text = "\n".join(missing_lines)
            chunks.append({
                "chunkId": f"raw_{ordinal + 1:06d}", "ordinal": ordinal,
                "text": recovery_text, "contextualText": recovery_text,
                "titlePath": [f"第 {page_no} 页"], "pageNo": page_no,
                "contentType": "text", "chunkStage": "raw", "sourceChunkIds": [],
                "metadata": {"parser": "pypdf", "sourceKind": "native_text_recovery", "sourceAnchor": {"pageNo": page_no}},
            })
        report.append({
            "pageNo": page_no, "nativeChars": len(native_chars),
            "parsedChars": len(_characters(parsed_text)),
            "nativeCoverage": round(coverage, 3), "nativeTextRecovered": recovered,
            "missingNativeChars": missing_chars,
            "needsReview": len(native_chars) < MIN_NATIVE_CHARS and not page_chunks,
        })
    return chunks, {
        "pageCount": len(pages), "pages": report,
        "recoveredPages": [item["pageNo"] for item in report if item["nativeTextRecovered"]],
        "reviewPages": [item["pageNo"] for item in report if item["needsReview"]],
    }


def _characters(text: str) -> Counter[str]:
    return Counter(re.findall(r"[\w\u3400-\u9fff]", text.lower()))


def _trigrams(text: str) -> Counter[str]:
    normalized = "".join(re.findall(r"[\w\u3400-\u9fff]", text.lower()))
    return Counter(normalized[index:index + 3] for index in range(max(0, len(normalized) - 2)))


def _coverage(expected: Counter[str], actual: Counter[str]) -> float:
    total = expected.total()
    return sum((expected & actual).values()) / total if total else 1.0


def _missing_lines(native_text: str, parsed_text: str) -> list[str]:
    available = _trigrams(parsed_text)
    missing = []
    for line in native_text.splitlines():
        line = line.strip()
        grams = _trigrams(line)
        if not grams:
            if _CRITICAL_VALUE.search(line) and line not in parsed_text:
                missing.append(line)
            continue
        if _coverage(grams, available) < 0.8:
            missing.append(line)
        else:
            available.subtract(grams)
    return missing
