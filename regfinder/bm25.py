# -*- coding: utf-8 -*-
from __future__ import annotations

import gc
import math
import re
from collections import Counter, defaultdict
from typing import Callable, DefaultDict, Dict, List, Tuple


class BM25Index:
    __slots__ = [
        "k1",
        "b",
        "corpus",
        "doc_lens",
        "avgdl",
        "idf",
        "N",
        "term_freq_by_doc",
        "postings",
    ]

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[List[str]] = []
        self.doc_lens: List[int] = []
        self.avgdl = 0.0
        self.idf: Dict[str, float] = {}
        self.N = 0
        self.term_freq_by_doc: List[Dict[str, int]] = []
        self.postings: DefaultDict[str, List[Tuple[int, int]]] = defaultdict(list)

    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        text = re.sub(r"[^\w\s가-힣]", " ", text.lower())
        tokens = text.split()
        particles = {"은", "는", "이", "가", "을", "를", "의", "에", "로", "와", "과", "도", "만"}
        filtered = []
        for token in tokens:
            if len(token) < 2:
                continue
            for particle in particles:
                if token.endswith(particle) and len(token) > len(particle) + 1:
                    token = token[:-len(particle)]
                    break
            if len(token) >= 2:
                filtered.append(token)
        return filtered

    def fit(self, docs: List[str]) -> None:
        self.corpus = []
        self.doc_lens = []
        self.term_freq_by_doc = []
        self.postings = defaultdict(list)
        df = Counter()
        for idx, doc in enumerate(docs):
            tokens = self._tokenize(doc)
            self.corpus.append(tokens)
            self.doc_lens.append(len(tokens))
            doc_tf = Counter(tokens)
            tf_dict = dict(doc_tf)
            self.term_freq_by_doc.append(tf_dict)
            df.update(tf_dict.keys())
            for term, tf in tf_dict.items():
                self.postings[term].append((idx, int(tf)))
        self.N = len(docs)
        self.avgdl = sum(self.doc_lens) / self.N if self.N else 0.0
        self.idf = {
            term: math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)
            for term, freq in df.items()
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        allow_doc: Callable[[int], bool] | None = None,
    ) -> List[Tuple[int, float]]:
        if not self.corpus or not query:
            return []
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []
        candidate_scores: Dict[int, float] = {}
        avgdl = self.avgdl if self.avgdl > 0 else 1.0
        for term in q_tokens:
            if term not in self.idf:
                continue
            for doc_idx, tf in self.postings.get(term, []):
                if allow_doc is not None and not allow_doc(doc_idx):
                    continue
                doc_len = self.doc_lens[doc_idx]
                num = tf * (self.k1 + 1)
                den = tf + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
                score = self.idf[term] * num / den if den > 0 else 0.0
                if score <= 0:
                    continue
                candidate_scores[doc_idx] = candidate_scores.get(doc_idx, 0.0) + score
        if not candidate_scores:
            return []
        return sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)[:top_k]

    def candidate_count(self, query: str, allow_doc: Callable[[int], bool] | None = None) -> int:
        if not self.corpus or not query:
            return 0
        q_tokens = self._tokenize(query)
        candidates: set[int] = set()
        for term in q_tokens:
            for doc_idx, _ in self.postings.get(term, []):
                if allow_doc is not None and not allow_doc(doc_idx):
                    continue
                candidates.add(doc_idx)
        return len(candidates)

    def clear(self) -> None:
        self.corpus.clear()
        self.doc_lens.clear()
        self.idf.clear()
        self.term_freq_by_doc.clear()
        self.postings.clear()
        gc.collect()


BM25Light = BM25Index
