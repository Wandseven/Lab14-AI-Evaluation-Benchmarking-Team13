"""
MainAgent mô phỏng RAG: retrieval (ranked chunk IDs) + generation.
V1: nhiễu xếp hạng → Hit Rate / MRR thấp hơn; V2: rerank + boost → tốt hơn.
"""
import asyncio
import hashlib
import math
import re
from typing import Dict, List, Tuple

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.knowledge_base import CHUNKS

# Giá ước lượng (USD / 1K tokens) — để báo cáo cost trong summary
_PRICE_PER_1K = 0.00015


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 1]


def _overlap_score(question: str, chunk_text: str) -> float:
    q = set(_tokenize(question))
    c = set(_tokenize(chunk_text))
    if not q or not c:
        return 0.0
    inter = len(q & c)
    return inter / (math.sqrt(len(q)) * math.sqrt(len(c)))


def _stable_seed(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


class MainAgent:
    def __init__(self, version: str = "v1"):
        self.name = f"SupportAgent-{version}"
        self.version = version
        self._chunks = list(CHUNKS)

    def _rank_chunks(self, question: str) -> List[Tuple[str, float]]:
        scored = [(c["id"], _overlap_score(question, c["text"])) for c in self._chunks]
        scored.sort(key=lambda x: -x[1])
        return scored

    def _apply_v1_noise(self, question: str, ranked: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """Giảm chất lượng retrieval: hoán vị nhẹ, giảm điểm top."""
        r = list(ranked)
        seed = _stable_seed(question)
        if len(r) >= 3 and seed % 4 != 0:
            # đổi chỗ phần tử đầu với vị trí 1–2
            j = 1 + (seed % 2)
            r[0], r[j] = r[j], r[0]
        if len(r) >= 2 and seed % 5 == 0:
            r[-1], r[-2] = r[-2], r[-1]
        return r

    def _rerank_v2(self, question: str, ranked: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """Tăng chất lượng: boost keyword trùng khóa học eval/rag."""
        boost_terms = {"rag", "mrr", "hit", "golden", "judge", "latency", "sla", "token", "eval", "chunk"}
        qset = set(_tokenize(question))
        out = []
        for cid, s in ranked:
            chunk = next(c for c in self._chunks if c["id"] == cid)
            extra = 0.05 * len(boost_terms & qset & set(_tokenize(chunk["text"])))
            out.append((cid, s + extra))
        out.sort(key=lambda x: -x[1])
        return out

    def _retrieve_ids(self, question: str, top_k: int = 8) -> List[str]:
        ranked = self._rank_chunks(question)
        if self.version == "v1":
            ranked = self._apply_v1_noise(question, ranked)
        else:
            ranked = self._rerank_v2(question, ranked)
        return [cid for cid, _ in ranked[:top_k]]

    def _compose_answer(self, question: str, retrieved_ids: List[str]) -> str:
        """Ưu tiên chunk rank 1; chỉ bổ sung chunk 2 khi V2 để tăng độ đầy đủ."""
        if not retrieved_ids:
            return "Theo tài liệu nội bộ, không tìm thấy đoạn phù hợp để trả lời."
        chunks_text: List[str] = []
        for cid in retrieved_ids[:2] if self.version == "v2" else retrieved_ids[:1]:
            c = next((x for x in self._chunks if x["id"] == cid), None)
            if c:
                chunks_text.append(c["text"])
        body = " ".join(chunks_text)[:900]
        if self.version == "v1" and _stable_seed(question) % 6 == 0:
            body = "Có thể có nhiều cách diễn giải. " + body
        intro = "Theo tài liệu nội bộ, "
        return intro + body[:800]

    async def query(self, question: str) -> Dict:
        await asyncio.sleep(0.02)
        retrieved_ids = self._retrieve_ids(question)
        answer = self._compose_answer(question, retrieved_ids)
        contexts = []
        k_ctx = 2 if self.version == "v2" else 1
        for cid in retrieved_ids[:k_ctx]:
            c = next((x for x in self._chunks if x["id"] == cid), None)
            if c:
                contexts.append(c["text"][:400])
        tokens_used = len(_tokenize(answer)) + len(_tokenize(question)) * 2 + 80
        cost_usd = (tokens_used / 1000.0) * _PRICE_PER_1K
        if self.version == "v1":
            tokens_used += 40  # giả lập prompt dài hơn / ít tối ưu
        return {
            "answer": answer,
            "retrieved_ids": retrieved_ids,
            "contexts": contexts,
            "metadata": {
                "model": "gpt-4o-mini-sim",
                "tokens_used": int(tokens_used),
                "cost_usd": round(cost_usd, 8),
                "sources": retrieved_ids[:3],
                "agent_version": self.version,
            },
        }


if __name__ == "__main__":
    async def _demo():
        a1 = MainAgent("v1")
        a2 = MainAgent("v2")
        q = "Hit Rate và MRR khác nhau thế nào?"
        print(await a1.query(q))
        print(await a2.query(q))

    asyncio.run(_demo())
