import asyncio
import time
from typing import Any, Dict, List


class BenchmarkRunner:
    def __init__(self, agent, evaluator, judge):
        self.agent = agent
        self.evaluator = evaluator
        self.judge = judge

    async def run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.perf_counter()

        response = await self.agent.query(test_case["question"])
        latency = time.perf_counter() - start_time

        ragas_scores = await self.evaluator.score(test_case, response)

        judge_result = await self.judge.evaluate_multi_judge(
            test_case["question"],
            response["answer"],
            test_case.get("expected_answer") or "",
        )

        final_score = judge_result["final_score"]
        return {
            "test_id": test_case.get("id"),
            "test_case": test_case["question"],
            "agent_response": response["answer"],
            "latency": round(latency, 4),
            "tokens_used": response.get("metadata", {}).get("tokens_used", 0),
            "cost_usd": response.get("metadata", {}).get("cost_usd", 0.0),
            "ragas": ragas_scores,
            "judge": judge_result,
            "retrieved_ids": response.get("retrieved_ids", []),
            "status": "fail" if final_score < 3.0 else "pass",
        }

    async def run_all(self, dataset: List[Dict[str, Any]], batch_size: int = 5) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for i in range(0, len(dataset), batch_size):
            batch = dataset[i : i + batch_size]
            tasks = [self.run_single_test(case) for case in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            for br in batch_results:
                if isinstance(br, Exception):
                    # Keep benchmark running even if one case hits transient API errors.
                    results.append(
                        {
                            "test_id": None,
                            "test_case": "[internal_error_case]",
                            "agent_response": "",
                            "latency": 0.0,
                            "tokens_used": 0,
                            "cost_usd": 0.0,
                            "ragas": {"faithfulness": 0.0, "relevancy": 0.0, "retrieval": {"hit_rate": 0.0, "mrr": 0.0}},
                            "judge": {
                                "final_score": 1.0,
                                "agreement_rate": 0.0,
                                "individual_scores": {"openai_judge": None, "gemini_judge": None},
                                "reasoning": f"exception: {type(br).__name__}",
                            },
                            "retrieved_ids": [],
                            "status": "fail",
                        }
                    )
                else:
                    results.append(br)
        return results
