"""
Multi-judge consensus using 2 OpenAI models.
Heuristic scores are used only as fallback when API/models are unavailable.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Tuple

from engine.llm_judge import LLMJudge, _judge_with_openai_optional
from engine.rater_metrics import buckets_1_to_5, position_bias_heuristic


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 1]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _to_1_5(x: float) -> float:
    return 1.0 + 4.0 * _clamp01(x)


def _lexical_score(answer: str, ground_truth: str) -> float:
    """Judge A: trùng từ với ground truth."""
    a, g = set(_tokenize(answer)), set(_tokenize(ground_truth))
    if not g:
        return 0.4
    return _clamp01(len(a & g) / max(1, len(g)))


def _structure_score(question: str, answer: str, ground_truth: str) -> float:
    """Judge B: độ đầy đủ + mức từ chối đúng khi GT yêu cầu từ chối."""
    a_low = answer.lower()
    gt_low = ground_truth.lower()
    refuse_terms = ("từ chối", "không có trong tài liệu", "không tìm thấy", "không được bịa")
    if any(t in gt_low for t in refuse_terms):
        bonus = 1.0 if any(t in a_low for t in refuse_terms) else 0.2
        return _clamp01(bonus)
    overlap = len(set(_tokenize(answer)) & set(_tokenize(ground_truth)))
    base = overlap / max(3, len(set(_tokenize(ground_truth))))
    len_pen = 1.0 if 20 <= len(answer) <= 1200 else 0.7
    return _clamp01(base * len_pen)


def _resolve_conflict(s1: float, s2: float) -> Tuple[float, float]:
    """Trả về (final_score_1_to_5, agreement_rate)."""
    d = abs(s1 - s2)
    if d <= 1.0:
        final = (s1 + s2) / 2.0
        agree = 1.0 - d / 4.0
        return final, _clamp01(agree)
    # Trọng tài thứ ba: lấy trung vị của hai điểm và điểm gần ground truth hơn (conservative min)
    conservative = min(s1, s2)
    median_like = (s1 + s2 + conservative) / 3.0
    final = max(1.0, min(5.0, median_like))
    agree = max(0.0, 1.0 - d / 5.0)
    return final, _clamp01(agree)


class MultiModelJudge:
    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        # Fallback heuristics
        h_lex = _to_1_5(_lexical_score(answer, ground_truth))
        h_struct = _to_1_5(_structure_score(question, answer, ground_truth))
        h_mean = (h_lex + h_struct) / 2.0

        # Primary pair: two OpenAI models (A/B)
        model_a = os.getenv("OPENAI_JUDGE_MODEL_A", "gpt-4o-mini")
        model_b = os.getenv("OPENAI_JUDGE_MODEL_B", "gpt-5-nano")
        score_a = await _judge_with_openai_optional(question, answer, ground_truth, model=model_a)
        score_b = await _judge_with_openai_optional(question, answer, ground_truth, model=model_b)

        # Choose two active raters with graceful fallback
        a_name, b_name = "openai_model_a", "openai_model_b"
        a = score_a if score_a is not None else h_mean
        b = score_b if score_b is not None else h_struct
        if score_a is None and score_b is None:
            a_name, b_name = "judge_lexical", "judge_structure"
            a, b = h_lex, h_struct

        final, agreement = _resolve_conflict(a, b)

        # Cohen's Kappa computed from the two active raters
        a_bucket = buckets_1_to_5(a)
        b_bucket = buckets_1_to_5(b)

        # Position bias: answer vs ground_truth, anchor = question (heuristic; LLM swap nếu POSITION_BIAS_LLM=1)
        if os.getenv("POSITION_BIAS_LLM", "").strip().lower() in ("1", "true", "yes"):
            pos = await LLMJudge().check_position_bias(answer, ground_truth, question)
        else:
            pos = position_bias_heuristic(answer, ground_truth, question)

        return {
            "final_score": round(final, 3),
            "agreement_rate": round(agreement, 4),
            "individual_scores": {
                f"{model_a}": round(score_a, 3) if score_a is not None else None,
                f"{model_b}": round(score_b, 3) if score_b is not None else None,
                "fallback_heuristic": round(h_mean, 3),
            },
            "rater_buckets": {f"{a_name}_1_5": a_bucket, f"{b_name}_1_5": b_bucket},
            "position_bias": pos,
            "reasoning": "Primary judges: OpenAI model A/B; heuristic fallback when needed.",
        }
