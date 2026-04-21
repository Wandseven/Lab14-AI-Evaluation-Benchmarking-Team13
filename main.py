"""
Chạy benchmark V1 vs V2, ghi reports/summary.json + benchmark_results.json.
"""
import asyncio
import json
import os
import time
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from agent.main_agent import MainAgent
from engine.consensus import MultiModelJudge
from engine.evaluator import ExpertEvaluator
from engine.rater_metrics import aggregate_position_bias_rate, cohens_kappa
from engine.runner import BenchmarkRunner


def _aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(results) or 1
    hit = sum(r["ragas"]["retrieval"]["hit_rate"] for r in results) / n
    mrr = sum(r["ragas"]["retrieval"]["mrr"] for r in results) / n
    faith = sum(r["ragas"]["faithfulness"] for r in results) / n
    rel = sum(r["ragas"]["relevancy"] for r in results) / n
    avg_score = sum(r["judge"]["final_score"] for r in results) / n
    agree = sum(r["judge"]["agreement_rate"] for r in results) / n
    total_tokens = sum(int(r.get("tokens_used") or 0) for r in results)
    total_cost = sum(float(r.get("cost_usd") or 0) for r in results)
    latencies = [float(r["latency"]) for r in results]
    return {
        "avg_score": round(avg_score, 4),
        "hit_rate": round(hit, 4),
        "mrr": round(mrr, 4),
        "faithfulness": round(faith, 4),
        "relevancy": round(rel, 4),
        "agreement_rate": round(agree, 4),
        "total_tokens": int(total_tokens),
        "total_cost_usd": round(total_cost, 6),
        "cost_per_eval_usd": round(total_cost / n, 8),
        "avg_latency_sec": round(sum(latencies) / n, 4),
        "p50_latency_sec": round(median(latencies), 4) if latencies else 0.0,
    }


def _rater_extras(results: List[Dict[str, Any]]) -> Dict[str, float]:
    """Cohen's Kappa (lexical vs structure bucket) + tổng hợp position bias heuristic."""
    y1: List[int] = []
    y2: List[int] = []
    for r in results:
        rb = (r.get("judge") or {}).get("rater_buckets")
        if rb and len(rb) >= 2:
            vals = list(rb.values())
            y1.append(int(vals[0]))
            y2.append(int(vals[1]))
    kappa = float(cohens_kappa(y1, y2)) if y1 else 0.0
    risk_rate, mean_delta = aggregate_position_bias_rate(results)
    return {
        "cohens_kappa": round(kappa, 4),
        "position_bias_risk_rate": round(risk_rate, 4),
        "position_bias_mean_delta": round(mean_delta, 4),
    }


def _release_decision(
    v1: Dict[str, Any], v2: Dict[str, Any]
) -> Tuple[str, str]:
    """Quyết định RELEASE / ROLLBACK / HOLD dựa trên delta và ngưỡng."""
    ds = v2["avg_score"] - v1["avg_score"]
    dh = v2["hit_rate"] - v1["hit_rate"]
    cost_ratio = (
        v2["cost_per_eval_usd"] / v1["cost_per_eval_usd"]
        if v1["cost_per_eval_usd"] > 0
        else 1.0
    )
    if ds < -0.2:
        return "ROLLBACK", f"avg_score drop {ds:+.3f} exceeds threshold."
    if dh < -0.08:
        return "ROLLBACK", f"hit_rate drop {dh:+.3f} (hallucination risk)."
    if cost_ratio > 2.2:
        return "HOLD", f"cost_per_eval up ~{cost_ratio:.2f}x; review caching/batch."
    if ds >= 0 or (ds >= -0.05 and dh >= 0):
        return "RELEASE", "Quality flat/up within tolerance; cost acceptable."
    return "HOLD", "Unclear improvement vs V1."


async def run_benchmark_with_results(agent_label: str, agent_version: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    print(f"[benchmark] agent={agent_label} ({agent_version})")

    if not os.path.exists("data/golden_set.jsonl"):
        print("[error] Missing data/golden_set.jsonl. Run: python data/synthetic_gen.py")
        return [], {}

    with open("data/golden_set.jsonl", "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]

    if not dataset:
        print("[error] golden_set.jsonl is empty.")
        return [], {}

    runner = BenchmarkRunner(MainAgent(agent_version), ExpertEvaluator(top_k=5), MultiModelJudge())
    results = await runner.run_all(dataset)
    metrics = _aggregate(results)
    metrics.update(_rater_extras(results))
    summary = {
        "metadata": {
            "version": agent_label,
            "agent_version": agent_version,
            "total": len(results),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "metrics": metrics,
    }
    return results, summary


async def main() -> None:
    v1_results, v1_summary = await run_benchmark_with_results("Agent_V1_Base", "v1")
    v2_results, v2_summary = await run_benchmark_with_results("Agent_V2_Optimized", "v2")

    if not v1_summary or not v2_summary:
        print("[error] Benchmark failed.")
        return

    decision, reason = _release_decision(v1_summary["metrics"], v2_summary["metrics"])

    regression = {
        "v1_metrics": v1_summary["metrics"],
        "v2_metrics": v2_summary["metrics"],
        "delta": {
            "avg_score": round(
                v2_summary["metrics"]["avg_score"] - v1_summary["metrics"]["avg_score"], 4
            ),
            "hit_rate": round(
                v2_summary["metrics"]["hit_rate"] - v1_summary["metrics"]["hit_rate"], 4
            ),
            "mrr": round(v2_summary["metrics"]["mrr"] - v1_summary["metrics"]["mrr"], 4),
            "cost_per_eval_usd": round(
                v2_summary["metrics"]["cost_per_eval_usd"]
                - v1_summary["metrics"]["cost_per_eval_usd"],
                8,
            ),
            "cohens_kappa": round(
                v2_summary["metrics"].get("cohens_kappa", 0)
                - v1_summary["metrics"].get("cohens_kappa", 0),
                4,
            ),
            "position_bias_risk_rate": round(
                v2_summary["metrics"].get("position_bias_risk_rate", 0)
                - v1_summary["metrics"].get("position_bias_risk_rate", 0),
                4,
            ),
        },
        "release_decision": decision,
        "release_reason": reason,
    }

    out_summary = {
        "metadata": {
            **v2_summary["metadata"],
            "primary_benchmark": "v2",
            "regression": regression,
        },
        "metrics": v2_summary["metrics"],
    }

    os.makedirs("reports", exist_ok=True)
    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(out_summary, f, ensure_ascii=False, indent=2)
    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "v1": v1_results,
                "v2": v2_results,
                "regression": regression,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n--- REGRESSION (V1 vs V2) ---")
    print(json.dumps(regression, ensure_ascii=False, indent=2))
    print(f"\nDecision: {decision}\nReason: {reason}")


if __name__ == "__main__":
    asyncio.run(main())
