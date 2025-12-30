from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable


@lru_cache(maxsize=2048)
def _compiled_word_pattern(keyword: str) -> re.Pattern[str]:
    # Word-boundary-ish match for ASCII-ish keywords. We avoid matching substrings
    # like "promo" in "promotes" or "intern" in "internal".
    return re.compile(r"(?<![A-Za-z0-9_])" + re.escape(keyword) + r"(?![A-Za-z0-9_])", re.IGNORECASE)


def keyword_in_text(text: str, keyword: str) -> bool:
    if not text or not keyword:
        return False

    k = str(keyword).strip()
    if not k:
        return False

    # For multi-word phrases (or punctuation-heavy patterns), substring is usually intended.
    if any(ch in k for ch in (" ", "-", "/", ":")):
        return k.lower() in text.lower()

    return _compiled_word_pattern(k).search(text) is not None


def any_keyword(text: str, keywords: Iterable[str]) -> bool:
    if not text:
        return False
    for k in keywords:
        if keyword_in_text(text, str(k)):
            return True
    return False
