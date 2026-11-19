import asyncio
import json
import math
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from groq import AsyncGroq, RateLimitError
from sentence_transformers import SentenceTransformer

from src.database.queries import search_knowledge
from src.models.schemas import SearchRequest
from src.agent.engine import run_agentic_loop

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
AGENT_MODEL = "openai/gpt-oss-120b"
JUDGE_MODEL = "openai/gpt-oss-20b"

embedder = SentenceTransformer("all-MiniLM-L6-v2")


def percentile(values: list[float], p: float) -> float:
    """Compute percentile (e.g., 50 or 95) from a list of floats."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)

async def call_groq_with_retry(**kwargs):
    """Retries automatically on Groq 429 RateLimitError with exponential backoff."""
    for attempt in range(5):
        try:
            return await groq_client.chat.completions.create(**kwargs)
        except RateLimitError as e:
            wait_s = 5 * (attempt + 1)
            print(f"   [⏳ Rate limit hit, waiting {wait_s}s before retry {attempt + 1}/5...]")
            await asyncio.sleep(wait_s)
    raise RuntimeError("Exceeded max retries for Groq RateLimitError")

async def run_plain_llm_baseline(query: str) -> tuple[str, float]:
    """Runs the raw query against the LLM with NO RAG context, NO tools, and NO guardrails."""
    start = time.perf_counter()
    res = await call_groq_with_retry(
            model=AGENT_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful banking support assistant."},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
        )
    return res.choices[0].message.content or "", time.perf_counter() - start


async def llm_as_a_judge(actual_response: str, expected_outcome: str, keywords: list) -> dict:
    prompt = f"""
    You are an objective evaluation judge for a banking AI.
    
    EXPECTED OUTCOME: {expected_outcome}
    REQUIRED KEYWORDS (semantic match): {keywords}
    
    ACTUAL AI RESPONSE:
    "{actual_response}"
    
    Score the response on two metrics (boolean true/false):
    1. faithfulness: Does the response strictly stick to facts/policies without hallucinating?
    2. resolution_accuracy: Does the response achieve the expected outcome and cover the semantic meaning of the keywords?
    
    Output strictly in JSON format: {{"faithfulness": true, "resolution_accuracy": false}}
    """
    res = await call_groq_with_retry(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    return json.loads(res.choices[0].message.content)


async def run_golden_set_evals():
    print("🚀 Starting LLMOps Evaluation Pipeline (Agent vs. Plain-LLM Baseline)...\n")

    with open("src/evals/golden_set.json", "r") as f:
        test_cases = json.load(f)

    total = len(test_cases)
    agent_scores = {
        "retrieval_hits": 0,
        "tool_accuracy": 0,
        "faithfulness": 0,
        "resolution_accuracy": 0,
        "latencies": [],
    }
    baseline_scores = {
        "faithfulness": 0,
        "resolution_accuracy": 0,
        "latencies": [],
    }

    for tc in test_cases:
        print(f"Running {tc['test_id']} [{tc['category']}]...")

        # --- 1. RAG RETRIEVAL ---
        search_req = SearchRequest(query=tc["input_query"], top_k=4)
        retrieved_chunks = search_knowledge(search_req, embedder)
        retrieved_doc_names = [chunk.document_name for chunk in retrieved_chunks]

        expected_docs = tc["expected_metrics"].get("rag_documents", [])
        hit = all(doc in retrieved_doc_names for doc in expected_docs) if expected_docs else True
        if hit:
            agent_scores["retrieval_hits"] += 1

        context_text = "\n".join([c.text for c in retrieved_chunks])

        # --- 2. UPI SENTINEL AGENT (Timed) ---
        actual_tools_called = []
        final_text = ""

        start_time = time.perf_counter()
        async for chunk in run_agentic_loop(
            query=tc["input_query"],
            context_text=context_text,
            user_role=tc["user_role"],
        ):
            if chunk["type"] == "tool":
                tool_name = chunk["content"].replace("Running ", "").replace("...", "")
                actual_tools_called.append(tool_name)
            elif chunk["type"] == "token":
                final_text += chunk["content"]
        agent_latency = time.perf_counter() - start_time
        agent_scores["latencies"].append(agent_latency)

        expected_tools = [t["function_name"] for t in tc["expected_metrics"].get("tool_calls", [])]
        if actual_tools_called == expected_tools:
            agent_scores["tool_accuracy"] += 1
        else:
            print(f"   [!] TOOL MISMATCH: Expected {expected_tools} | Got {actual_tools_called}")

        agent_judgement = await llm_as_a_judge(
            actual_response=final_text,
            expected_outcome=tc["expected_metrics"]["outcome"],
            keywords=tc["expected_metrics"]["ideal_response_keywords"],
        )
        if agent_judgement.get("faithfulness"):
            agent_scores["faithfulness"] += 1
        if agent_judgement.get("resolution_accuracy"):
            agent_scores["resolution_accuracy"] += 1
        else:
            print(f"   [!] AGENT RESOLUTION FAILED ({agent_latency:.2f}s): \"{final_text[:120]}...\"")

        # --- 3. PLAIN-LLM BASELINE (Timed) ---
        baseline_text, baseline_latency = await run_plain_llm_baseline(tc["input_query"])
        baseline_scores["latencies"].append(baseline_latency)

        baseline_judgement = await llm_as_a_judge(
            actual_response=baseline_text,
            expected_outcome=tc["expected_metrics"]["outcome"],
            keywords=tc["expected_metrics"]["ideal_response_keywords"],
        )
        if baseline_judgement.get("faithfulness"):
            baseline_scores["faithfulness"] += 1
        if baseline_judgement.get("resolution_accuracy"):
            baseline_scores["resolution_accuracy"] += 1
        await asyncio.sleep(5)

    # --- COMPUTE FINAL METRICS ---
    retrieval_pct = (agent_scores["retrieval_hits"] / total) * 100
    tool_pct = (agent_scores["tool_accuracy"] / total) * 100
    agent_faith_pct = (agent_scores["faithfulness"] / total) * 100
    agent_res_pct = (agent_scores["resolution_accuracy"] / total) * 100
    agent_p50 = percentile(agent_scores["latencies"], 50)
    agent_p95 = percentile(agent_scores["latencies"], 95)

    base_faith_pct = (baseline_scores["faithfulness"] / total) * 100
    base_res_pct = (baseline_scores["resolution_accuracy"] / total) * 100
    base_p50 = percentile(baseline_scores["latencies"], 50)
    base_p95 = percentile(baseline_scores["latencies"], 95)

    # --- PRINT README-READY MARKDOWN TABLE ---
    print("\n" + "=" * 60)
    print("🏆 EVALUATION REPORT (COPY-PASTE INTO README.md)")
    print("=" * 60)
    print(f"| Metric ({total} Golden Cases) | Plain LLM Baseline | UPI Sentinel Agent | Delta |")
    print("| :--- | :---: | :---: | :---: |")
    print(f"| **Retrieval Hit Rate** | N/A | **{retrieval_pct:.1f}%** | — |")
    print(f"| **Tool-Call Accuracy** | 0.0% | **{tool_pct:.1f}%** | +{tool_pct:.1f}% |")
    print(f"| **Faithfulness** | {base_faith_pct:.1f}% | **{agent_faith_pct:.1f}%** | {agent_faith_pct - base_faith_pct:+.1f}% |")
    print(f"| **Resolution Accuracy** | {base_res_pct:.1f}% | **{agent_res_pct:.1f}%** | {agent_res_pct - base_res_pct:+.1f}% |")
    print(f"| **P50 Latency** | {base_p50:.2f}s | **{agent_p50:.2f}s** | {agent_p50 - base_p50:+.2f}s |")
    print(f"| **P95 Latency** | {base_p95:.2f}s | **{agent_p95:.2f}s** | {agent_p95 - base_p95:+.2f}s |")
    print("=" * 60)

    # --- CI QUALITY GATES ---
    print("\n[CI GATE] Checking production thresholds...")
    failed = False
    if retrieval_pct < 85.0:
        print("❌ FAILED: Retrieval Hit Rate < 85.0%")
        failed = True
    if tool_pct < 90.0:
        print("❌ FAILED: Tool-Call Accuracy < 90.0%")
        failed = True
    if agent_faith_pct < 90.0:
        print("❌ FAILED: Faithfulness < 90.0%")
        failed = True
    if agent_res_pct < 85.0:
        print("❌ FAILED: Resolution Accuracy < 85.0%")
        failed = True
    if agent_p95 > 8.0:
        print(f"⚠️ WARNING: P95 Latency ({agent_p95:.2f}s) exceeded 8.0s target.")

    if failed:
        print("\n🚨 LLMOps Pipeline Blocked: Regressions detected.")
        sys.exit(1)
    else:
        print("\n✅ All metrics passed! Ready for production deployment.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(run_golden_set_evals())