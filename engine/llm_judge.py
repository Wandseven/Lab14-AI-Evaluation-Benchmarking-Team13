"""
LLM Judge helpers for OpenAI models.
If API keys are missing, callers should fallback to heuristic judges.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore

from engine.rater_metrics import position_bias_heuristic

_LOGGED_WARNINGS: set[str] = set()


def _warn_once(key: str, message: str) -> None:
    if key in _LOGGED_WARNINGS:
        return
    _LOGGED_WARNINGS.add(key)
    print(f"[judge-warning] {message}")


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


def _is_retryable_error(e: Exception) -> bool:
    msg = str(e).upper()
    return ("503" in msg) or ("UNAVAILABLE" in msg) or ("429" in msg) or ("RESOURCE_EXHAUSTED" in msg)


def _extract_float_1_5(text: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*/\s*5|score\D*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        v = float(m.group(1) or m.group(2))
        return max(1.0, min(5.0, v))
    m2 = re.search(r"\b([1-5])(?:\.\d+)?\b", text)
    if m2:
        return float(m2.group(1))
    return None


async def _judge_with_openai_optional(
    question: str, answer: str, ground_truth: str, model: Optional[str] = None
) -> Optional[float]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        _warn_once("openai-key-missing", "OPENAI_API_KEY is missing; OpenAI judge disabled.")
        return None
    if AsyncOpenAI is None:
        _warn_once("openai-sdk-missing", "openai SDK is unavailable; OpenAI judge disabled.")
        return None
    client = AsyncOpenAI(api_key=key)
    prompt = (
        "Bạn là judge. Chấm độ khớp của câu trả lời với ground truth (1-5).\n"
        "5=khớp hoàn toàn; 1= sai hoặc hallucination.\n"
        f"Question: {question}\nGround truth: {ground_truth}\nAnswer: {answer}\n"
        "Trả lời JSON: {\"score\": số từ 1 đến 5}"
    )
    timeout_sec = _env_float("JUDGE_API_TIMEOUT_SEC", 20.0)
    max_retry = int(_env_float("JUDGE_RETRY_COUNT", 1))
    for attempt in range(max_retry + 1):
        try:
            resp = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model or os.getenv("OPENAI_JUDGE_MODEL", "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_completion_tokens=80,
                ),
                timeout=timeout_sec,
            )
            raw = resp.choices[0].message.content or ""
            try:
                data = json.loads(raw)
                s = float(data.get("score", 3))
                return max(1.0, min(5.0, s))
            except json.JSONDecodeError:
                return _extract_float_1_5(raw)
        except Exception as e:
            retryable = _is_retryable_error(e) or isinstance(e, asyncio.TimeoutError)
            if retryable and attempt < max_retry:
                await asyncio.sleep(1.5 * (attempt + 1))
                continue
            _warn_once("openai-api-error", f"OpenAI judge failed: {type(e).__name__}: {e}")
            return None
    return None


async def _llm_pairwise_preference(
    client: Any, model: str, ref: str, text_a: str, text_b: str, a_label: str = "A", b_label: str = "B"
) -> Optional[int]:
    """Trả về 1 nếu A tốt hơn, 2 nếu B tốt hơn, None nếu lỗi."""
    prompt = (
        "So sánh hai phương án trả lời dưới đây với REFERENCE (ground truth).\n"
        "Trả lời JSON duy nhất: {\"better\": 1 hoặc 2} (1 = phương án 1 tốt hơn).\n\n"
        f"REFERENCE:\n{ref[:1200]}\n\n"
        f"PHUONG_AN_1 ({a_label}):\n{text_a[:800]}\n\n"
        f"PHUONG_AN_2 ({b_label}):\n{text_b[:800]}\n"
    )
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_completion_tokens=60,
        )
        raw = resp.choices[0].message.content or ""
        data = json.loads(raw)
        v = int(data.get("better", 0))
        return v if v in (1, 2) else None
    except Exception:
        return None


class LLMJudge:
    """Giữ lại class mẫu — logic chính nằm ở consensus.MultiModelJudge."""

    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.rubrics: Dict[str, str] = {
            "accuracy": "Chấm 1-5 so với Ground Truth.",
            "tone": "Chấm 1-5 về mức độ chuyên nghiệp.",
        }

    async def evaluate_multi_judge(self, question: str, answer: str, ground_truth: str) -> Dict[str, Any]:
        s = await _judge_with_openai_optional(question, answer, ground_truth)
        if s is None:
            s = 3.0
        return {
            "final_score": s,
            "agreement_rate": 1.0,
            "individual_scores": {self.model: s},
        }

    async def check_position_bias(
        self, response_a: str, response_b: str, anchor: str = ""
    ) -> Dict[str, Any]:
        """Position bias check (heuristic by default, optional OpenAI swap test)."""
        anchor = anchor or (response_a + " " + response_b)[:400]
        base = position_bias_heuristic(response_a, response_b, anchor)

        use_llm = os.getenv("POSITION_BIAS_LLM", "").strip() in ("1", "true", "yes")
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not (use_llm and key and AsyncOpenAI is not None):
            return {**base, "llm_swap_test": None}

        client = AsyncOpenAI(api_key=key)
        model = os.getenv("OPENAI_JUDGE_MODEL", "gpt-4o-mini")
        ref = anchor[:1200]
        pref1 = await _llm_pairwise_preference(client, model, ref, response_a, response_b, "1", "2")
        pref2 = await _llm_pairwise_preference(client, model, ref, response_b, response_a, "1", "2")
        # pref1: 1=A tốt hơn khi (A,B). pref2: 1=B tốt hơn khi (B,A) tức A là option 2 -> A tốt hơn thì pref2=2.
        # Không thiên vị vị trí: pref1 + pref2 == 3.
        bias_llm = None
        if pref1 is not None and pref2 is not None:
            bias_llm = pref1 + pref2 != 3
        return {
            **base,
            "llm_swap_test": {
                "prefer_when_ab_order": pref1,
                "prefer_when_ba_order": pref2,
                "bias_llm_inconsistent": bias_llm,
            },
        }
