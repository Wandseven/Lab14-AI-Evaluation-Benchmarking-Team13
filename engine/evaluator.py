"""
ExpertEvaluator: faithfulness / relevancy + retrieval (Hit Rate, MRR).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from engine.retrieval_eval import RetrievalEvaluator


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 1]


class ExpertEvaluator:
    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self._retrieval = RetrievalEvaluator()

    def _faithfulness(self, answer: str, contexts: List[str]) -> float:
        if not contexts:
            return 0.35
        bag = set()
        for c in contexts:
            bag |= set(_tokenize(c))
        aw = set(_tokenize(answer))
        if not aw:
            return 0.0
        inter = len(aw & bag)
        return max(0.0, min(1.0, inter / max(1, len(aw))))

    def _relevancy(self, question: str, answer: str, expected: str) -> float:
        q, a, e = set(_tokenize(question)), set(_tokenize(answer)), set(_tokenize(expected))
        if not e:
            return 0.5
        # Trùng với ground truth và câu hỏi
        num = len(a & e) + 0.5 * len(a & q)
        den = max(1, len(e))
        return max(0.0, min(1.0, num / den))

    async def score(self, case: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        expected_ids = case.get("expected_retrieval_ids") or []
        retrieved_ids = response.get("retrieved_ids") or []
        hit = self._retrieval.calculate_hit_rate(expected_ids, retrieved_ids, top_k=self.top_k)
        mrr = self._retrieval.calculate_mrr(expected_ids, retrieved_ids)
        contexts = response.get("contexts") or []
        answer = response.get("answer") or ""
        faith = self._faithfulness(answer, contexts)
        rel = self._relevancy(case.get("question", ""), answer, case.get("expected_answer", ""))
        return {
            "faithfulness": round(faith, 4),
            "relevancy": round(rel, 4),
            "retrieval": {"hit_rate": float(hit), "mrr": float(mrr)},
        }
