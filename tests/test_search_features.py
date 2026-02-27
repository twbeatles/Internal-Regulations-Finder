# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

from regfinder.qa_system import RegulationQASystem


class SearchFeatureTest(unittest.TestCase):
    def setUp(self):
        self.qa = RegulationQASystem()
        self.sample = [
            {"source": "휴가규정.pdf", "path": "C:/reg/휴가규정.pdf", "score": 0.9, "mtime": 100.0},
            {"source": "인사규정.docx", "path": "C:/reg/인사규정.docx", "score": 0.7, "mtime": 200.0},
            {"source": "복리후생.txt", "path": "C:/reg/sub/복리후생.txt", "score": 0.8, "mtime": 150.0},
        ]

    def test_extension_filter(self):
        out = self.qa._apply_search_filters(self.sample, {"extension": ".pdf", "filename": "", "path": ""})
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["source"].endswith(".pdf"))

    def test_filename_filter(self):
        out = self.qa._apply_search_filters(self.sample, {"extension": "", "filename": "인사", "path": ""})
        self.assertEqual(len(out), 1)
        self.assertIn("인사", out[0]["source"])

    def test_sort_by_filename(self):
        out = self.qa._sort_results(self.sample, "filename_asc")
        names = [x["source"] for x in out]
        self.assertEqual(names, sorted(names, key=lambda x: x.lower()))

    def test_sort_by_mtime_desc(self):
        out = self.qa._sort_results(self.sample, "mtime_desc")
        self.assertEqual(out[0]["mtime"], 200.0)


if __name__ == "__main__":
    unittest.main()
