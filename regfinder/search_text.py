# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Iterable, List


_KOREAN_PARTICLES = {
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "로",
    "와",
    "과",
    "도",
    "만",
}


def normalize_path_text(value: str) -> str:
    text = str(value or "").strip().lower().replace("\\", "/")
    text = re.sub(r"/{2,}", "/", text)
    return text


def normalize_search_text(value: str) -> str:
    text = re.sub(r"[^\w\s가-힣]", " ", str(value or "").lower())
    return " ".join(text.split())


def normalize_compact_text(value: str) -> str:
    return normalize_search_text(value).replace(" ", "")


def _strip_particle(token: str) -> str:
    for particle in _KOREAN_PARTICLES:
        if token.endswith(particle) and len(token) > len(particle) + 1:
            return token[: -len(particle)]
    return token


def semantic_terms(value: str) -> List[str]:
    terms: List[str] = []
    seen: set[str] = set()
    for raw in normalize_search_text(value).split():
        token = _strip_particle(raw)
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def bm25_terms(value: str) -> List[str]:
    terms = list(semantic_terms(value))
    seen = set(terms)
    expanded: List[str] = list(terms)
    for token in terms:
        if len(token) < 4 or not re.fullmatch(r"[가-힣]+", token):
            continue
        for n in (2, 3):
            if len(token) < n:
                continue
            for idx in range(len(token) - n + 1):
                gram = token[idx: idx + n]
                if gram in seen:
                    continue
                seen.add(gram)
                expanded.append(gram)
    return expanded


def highlight_terms(value: str) -> List[str]:
    return sorted(semantic_terms(value), key=len, reverse=True)


def matches_text_filter(value: str, query: str) -> bool:
    terms = semantic_terms(query)
    if not terms:
        return True
    normalized = normalize_search_text(value)
    compact = normalized.replace(" ", "")
    return all(term in normalized or term in compact for term in terms)


def matches_path_filter(value: str, query: str) -> bool:
    normalized_value = normalize_path_text(value)
    normalized_query = normalize_path_text(query)
    if not normalized_query:
        return True
    return normalized_query in normalized_value


def repeated_title_text(source: str, content: str, *, repeats: int = 2) -> str:
    prefix = " ".join(str(source or "") for _ in range(max(0, repeats))).strip()
    if prefix:
        return f"{prefix} {content}".strip()
    return str(content or "").strip()


def unique_terms(values: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or "")
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered
