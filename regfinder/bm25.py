# -*- coding: utf-8 -*-
from __future__ import annotations

import gc
import math
import re
from collections import Counter
from typing import Dict, List, Tuple

class BM25Light:
    __slots__ = ['k1', 'b', 'corpus', 'doc_lens', 'avgdl', 'idf', 'N']
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[List[str]] = []
        self.doc_lens: List[int] = []
        self.avgdl = 0.0
        self.idf: Dict[str, float] = {}
        self.N = 0
    
    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        # 특수문자 제거 및 소문자화
        text = re.sub(r'[^\w\s가-힣]', ' ', text.lower())
        tokens = text.split()
        
        # 한국어 조사 필터링 (간이)
        particles = {'은', '는', '이', '가', '을', '를', '의', '에', '로', '와', '과', '도', '만'}
        filtered = []
        for t in tokens:
            if len(t) < 2: continue
            # 조사가 붙어있는 경우 제거 시도
            for p in particles:
                if t.endswith(p) and len(t) > len(p) + 1:
                    t = t[:-len(p)]
                    break
            if len(t) >= 2:
                filtered.append(t)
        return filtered
    
    def fit(self, docs: List[str]):
        self.corpus = []
        self.doc_lens = []
        df = Counter()
        for doc in docs:
            tokens = self._tokenize(doc)
            self.corpus.append(tokens)
            self.doc_lens.append(len(tokens))
            df.update(set(tokens))
        self.N = len(docs)
        self.avgdl = sum(self.doc_lens) / self.N if self.N else 0
        self.idf = {t: math.log((self.N - f + 0.5) / (f + 0.5) + 1) for t, f in df.items()}
        del df
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        if not self.corpus or not query:
            return []
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []
        scores = []
        for idx, doc_tokens in enumerate(self.corpus):
            if not doc_tokens:
                continue
            score = self._score(q_tokens, doc_tokens, self.doc_lens[idx])
            if score > 0:
                scores.append((idx, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    def _score(self, query: List[str], doc: List[str], doc_len: int) -> float:
        score = 0.0
        doc_tf = Counter(doc)
        for term in query:
            if term not in self.idf:
                continue
            tf = doc_tf.get(term, 0)
            idf = self.idf[term]
            num = tf * (self.k1 + 1)
            avgdl = self.avgdl if self.avgdl > 0 else 1.0  # Division by zero 방어
            den = tf + self.k1 * (1 - self.b + self.b * doc_len / avgdl)
            score += idf * num / den if den > 0 else 0
        return score
    
    def clear(self):
        self.corpus.clear()
        self.doc_lens.clear()
        self.idf.clear()
        gc.collect()
