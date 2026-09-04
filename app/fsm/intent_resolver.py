from __future__ import annotations

import re

from .models import Intent


class IntentResolver:
    _ADD_PRODUCT_PATTERNS: tuple[str, ...] = (
        r"\badd\s+product\b",
        r"\b(add|create|new|register|enter|stock)\b.*\b(product|item)\b",
        r"\b(product|item)\b.*\b(add|create|new|register|enter|stock)\b",
    )
    _RECORD_SALE_PATTERNS: tuple[str, ...] = (
        r"\brecord\s+sale\b",
        r"\b(add|record|create|new|log|capture|sell|sold)\b.*\b(sale|transaction|payment)\b",
        r"\b(sale|transaction|payment)\b.*\b(add|record|create|new|log|capture|sell|sold)\b",
    )

    _GENERATE_REPORT_PATTERNS: tuple[str, ...] = (
        r"\bgenerate\s+report\b",
        r"\b(generate|create|get|send|show|view|nataka|nipe)\b.*\b(report|ripoti|summary)\b",
        r"\b(report|ripoti)\b.*\b(generate|create|get|send|show|view|nataka|nipe)\b",
        r"\b(daily report|sales report|summary report)\b",
    )

    def resolve(self, text: str) -> Intent:
        normalized = " ".join(text.lower().strip().split())

        if not normalized:
            return Intent.UNKNOWN

        if self._matches_any(normalized, self._ADD_PRODUCT_PATTERNS):
            return Intent.ADD_PRODUCT

        if self._matches_any(normalized, self._RECORD_SALE_PATTERNS):
            return Intent.RECORD_SALE

        if self._matches_any(normalized, self._GENERATE_REPORT_PATTERNS):
            return Intent.GENERATE_REPORT

        return Intent.UNKNOWN

    def _matches_any(self, text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)
