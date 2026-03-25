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

    def test_filename_filter_matches_compact_query_against_spaced_filename(self):
        sample = [
            {"source": "인사 규정.docx", "path": r"C:\reg\인사 규정.docx", "score": 0.7, "mtime": 200.0},
        ]
        out = self.qa._apply_search_filters(sample, {"extension": "", "filename": "인사규정", "path": ""})
        self.assertEqual(len(out), 1)

    def test_path_filter_accepts_forward_slash_for_windows_style_path(self):
        sample = [
            {"source": "휴가규정.pdf", "path": r"C:\reg\hr\휴가규정.pdf", "score": 0.9, "mtime": 100.0},
        ]
        out = self.qa._apply_search_filters(sample, {"extension": "", "filename": "", "path": "reg/hr"})
        self.assertEqual(len(out), 1)

    def test_sort_by_filename(self):
        out = self.qa._sort_results(self.sample, "filename_asc")
        names = [x["source"] for x in out]
        self.assertEqual(names, sorted(names, key=lambda x: x.lower()))

    def test_sort_by_mtime_desc(self):
        out = self.qa._sort_results(self.sample, "mtime_desc")
        self.assertEqual(out[0]["mtime"], 200.0)

    def test_aggregate_file_results_collects_matched_chunk_indices(self):
        aggregated = self.qa._aggregate_file_results(
            [
                {
                    "id": "file-a#2",
                    "file_key": "file-a",
                    "chunk_idx": 2,
                    "content": "두 번째 청크",
                    "source": "휴가규정.pdf",
                    "path": "C:/reg/휴가규정.pdf",
                    "mtime": 100.0,
                    "vec_score": 0.8,
                    "bm25_score": 0.3,
                },
                {
                    "id": "file-a#0",
                    "file_key": "file-a",
                    "chunk_idx": 0,
                    "content": "첫 번째 청크",
                    "source": "휴가규정.pdf",
                    "path": "C:/reg/휴가규정.pdf",
                    "mtime": 100.0,
                    "vec_score": 0.5,
                    "bm25_score": 0.9,
                },
            ],
            search_mode="hybrid",
        )

        self.assertEqual(len(aggregated), 1)
        self.assertEqual(aggregated[0]["match_count"], 2)
        self.assertEqual(aggregated[0]["matched_chunk_indices"], [0, 2])
        self.assertEqual(aggregated[0]["matched_doc_ids"], ["file-a#0", "file-a#2"])

    def test_get_chunks_for_file_key_returns_sorted_chunks(self):
        self.qa.documents = ["세 번째", "첫 번째", "두 번째"]
        self.qa.doc_meta = [
            {"id": "file-a#2", "file_key": "file-a", "chunk_idx": 2, "source": "규정.pdf", "path": "C:/reg/규정.pdf", "mtime": 3},
            {"id": "file-a#0", "file_key": "file-a", "chunk_idx": 0, "source": "규정.pdf", "path": "C:/reg/규정.pdf", "mtime": 3},
            {"id": "file-a#1", "file_key": "file-a", "chunk_idx": 1, "source": "규정.pdf", "path": "C:/reg/규정.pdf", "mtime": 3},
        ]

        chunks = self.qa.get_chunks_for_file_key("file-a")

        self.assertEqual([chunk["chunk_idx"] for chunk in chunks], [0, 1, 2])
        self.assertEqual([chunk["content"] for chunk in chunks], ["첫 번째", "두 번째", "세 번째"])


if __name__ == "__main__":
    unittest.main()
