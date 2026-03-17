# -*- coding: utf-8 -*-
from __future__ import annotations

from regfinder.ui_style import get_preferred_ui_font_family


def test_get_preferred_ui_font_family_prefers_malgun_gothic_on_windows():
    family = get_preferred_ui_font_family(
        platform_name="win32",
        available_families=["Segoe UI", "Malgun Gothic", "Arial"],
    )

    assert family == "Malgun Gothic"


def test_get_preferred_ui_font_family_accepts_korean_name_on_windows():
    family = get_preferred_ui_font_family(
        platform_name="win32",
        available_families=["맑은 고딕", "Segoe UI"],
    )

    assert family == "맑은 고딕"


def test_get_preferred_ui_font_family_is_disabled_off_windows():
    family = get_preferred_ui_font_family(
        platform_name="linux",
        available_families=["Malgun Gothic"],
    )

    assert family is None
