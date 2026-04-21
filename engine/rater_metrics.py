"""
Cohen's Kappa (hai rater nhãn rời rạc) và proxy Position Bias (độ nhạy thứ tự).
Không phụ thuộc sklearn.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Tuple


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 1]


def buckets_1_to_5(score: float) -> int:
    """Làm tròn điểm liên tục 1–5 thành nhãn rời rạc cho Kappa."""
    x = int(round(float(score)))
    return max(1, min(5, x))


def cohens_kappa(rater1: Sequence[int], rater2: Sequence[int]) -> float:
    """
    Cohen's Kappa cho hai rater, cùng n mẫu, nhãn nguyên (1–5).
    kappa = (p_o - p_e) / (1 - p_e)
    """
    if not rater1 or len(rater1) != len(rater2):
        return 0.0
    n = len(rater1)
    po = sum(1 for a, b in zip(rater1, rater2) if a == b) / n
    cats = sorted(set(rater1) | set(rater2))
    pe = 0.0
    for c in cats:
        p1 = sum(1 for x in rater1 if x == c) / n
        p2 = sum(1 for x in rater2 if x == c) / n
        pe += p1 * p2
    denom = 1.0 - pe
    if denom <= 1e-12:
        return 1.0 if po >= 1.0 - 1e-12 else 0.0
    return (po - pe) / denom


def first_window_overlap_with_anchor(merged: str, anchor: str, window_ratio: float = 0.55) -> float:
    """
    Jaccard giữa anchor và cửa sổ token đầu của merged (mô phỏng judge chỉ đọc phần đầu).
    """
    mt, at = _tokenize(merged), _tokenize(anchor)
    if not mt or not at:
        return 0.0
    aset = set(at)
    n = max(1, int(len(mt) * window_ratio))
    first = set(mt[:n])
    return len(first & aset) / max(1, len(aset))


def position_bias_heuristic(response_a: str, response_b: str, anchor: str) -> Dict[str, Any]:
    """
    Proxy Position Bias: so khớp anchor với phần đầu khi ghép (A||B) vs (B||A).
    Nếu delta lớn, thứ tự trình bày ảnh hưởng mạnh tới "điểm đọc nửa đầu" — rủi ro thiên vị vị trí.
    """
    if not anchor.strip():
        anchor = (response_a + " " + response_b)[:400]
    sep = "\n\n"
    m1 = response_a + sep + response_b
    m2 = response_b + sep + response_a
    o1 = first_window_overlap_with_anchor(m1, anchor)
    o2 = first_window_overlap_with_anchor(m2, anchor)
    delta = abs(o1 - o2)
    return {
        "order_overlap_delta": round(delta, 4),
        "overlap_a_first": round(o1, 4),
        "overlap_b_first": round(o2, 4),
        "position_bias_risk": bool(delta > 0.08),
        "method": "first_window_jaccard_vs_anchor",
    }


def aggregate_position_bias_rate(results: List[dict]) -> Tuple[float, float]:
    """(tỉ lệ case có risk, delta trung bình)."""
    n = len(results) or 1
    deltas = []
    risks = 0
    for r in results:
        pb = (r.get("judge") or {}).get("position_bias") or {}
        d = float(pb.get("order_overlap_delta") or 0.0)
        deltas.append(d)
        if pb.get("position_bias_risk"):
            risks += 1
    return risks / n, sum(deltas) / n
