# -*- coding: utf-8 -*-
from __future__ import annotations

from regfinder.search_text import bm25_terms, highlight_terms, matches_path_filter


def test_bm25_terms_support_compound_korean_query():
    terms = bm25_terms("휴가규정")

    assert "휴가규정" in terms
    assert "휴가" in terms
    assert "규정" in terms


def test_highlight_terms_strip_particles():
    assert highlight_terms("휴가를") == ["휴가"]


def test_matches_path_filter_normalizes_slashes():
    assert matches_path_filter(r"c:\docs\hr\휴가규정.pdf", "docs/hr") is True
