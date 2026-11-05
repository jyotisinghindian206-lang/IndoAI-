"""Opt-in local Ollama benchmark runner; never executes generated code."""
from __future__ import annotations
import json
import re
import time
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any
from .suite import CASES, validate_suite


def _normalize(value: str) -> str:
    raw = str(value).casefold()
    raw = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", raw)
    raw = re.sub(r"\bpercent\b", "%", raw)
    normalized = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%.-]+", " ", raw)).strip()
    return re.sub(r"(?<=\d)\s+%", "%", normalized)


def _contains_expected(text: str, expected: str) -> bool:
    needle = _normalize(expected)
    if not needle:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?%?", needle):
        return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", text) is not None
    return needle in text


def score_answer(case: dict[str, Any], answer: str) -> dict[str, Any]:
    mode = case.get("scoring")
    if mode == "human_review":
        return {"status": "needs_human_review", "score": None, "matched": [], "rubric": list(case.get("rubric") or []),
                "note": "Coding output is not executed; review correctness, safety, edge cases and tests."}
    if mode == "requires_vision_fixture":
        return {"status": "not_run_missing_vision_fixture", "score": None, "matched": [],
                "note": "Requires an actual image fixture and a vision-capable provider adapter."}
    text = _normalize(answer)
    expected = [str(x) for x in (case.get("expected") or [])]
    if mode == "contains_any":
        matched = [item for item in expected if _contains_expected(text, item)]
        passed = bool(matched)
        return {"status": "passed" if passed else "failed", "score": 1.0 if passed else 0.0, "matched": matched, "expected": expected}
    if mode == "all_terms":
        matched = [x for x in expected if _contains_expected(text, x)]
        passed = len(matched) == len(expected)
        return {"status": "passed" if passed else "failed", "score": len(matched) / max(1, len(expected)), "matched": matched, "expected": expected}
    return {"status": "not_scored_unknown_rule", "score": None, "matched": []}


def _ollama_generate(base_url: str, model: str, prompt: str, timeout: float) -> tuple[str, float]:
    payload = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": 0, "seed": 42}}
    request = urllib.request.Request(base_url.rstrip("/") + "/api/generate", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read(8 * 1024 * 1024).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {detail[:300]}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Ollama is unreachable. Start it and check INDO_OLLAMA_BASE_URL.") from exc
    elapsed = (time.perf_counter() - started) * 1000
    answer = data.get("response") if isinstance(data, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("Ollama returned an empty or invalid response.")
    return answer.strip(), elapsed


def run_local_benchmark(*, base_url: str, model: str, limit: int = 10, offset: int = 0,
                        categories: list[str] | None = None, timeout: float = 120.0) -> dict[str, Any]:
    """Run a bounded benchmark against local Ollama; no cloud keys used."""
    suite_status = validate_suite()
    if not suite_status["valid"]:
        raise RuntimeError("Benchmark manifest validation failed.")
    limit = max(1, min(int(limit), 140))
    offset = max(0, min(int(offset), 139))
    timeout = max(5.0, min(float(timeout), 300.0))
    selected_categories = set(categories or [])
    unknown = selected_categories - set(suite_status["category_counts"])
    if unknown:
        raise ValueError("Unknown benchmark categories: " + ", ".join(sorted(unknown)))
    filtered = [c for c in CASES if not selected_categories or c["category"] in selected_categories]
    selected = filtered[offset:offset + limit]
    results = []
    for case in selected:
        if case.get("requires_attachment"):
            results.append({"id": case["id"], "category": case["category"], "status": "not_run_missing_vision_fixture",
                            "score": None, "note": "No image fixture supplied; no vision capability claim is made."})
            continue
        try:
            answer, latency_ms = _ollama_generate(base_url, model, case["prompt"], timeout)
            scored = score_answer(case, answer)
            results.append({"id": case["id"], "category": case["category"], "status": scored["status"],
                            "score": scored["score"], "latency_ms": round(latency_ms, 1), "answer": answer[:6000], "scoring": scored})
        except Exception as exc:
            results.append({"id": case["id"], "category": case["category"], "status": "error", "score": None,
                            "error": f"{type(exc).__name__}: {str(exc)[:400]}"})
    grouped = defaultdict(list)
    for item in results: grouped[item["category"]].append(item)
    category_summary = {}
    for category, items in grouped.items():
        objective = [x for x in items if x.get("score") is not None]
        category_summary[category] = {"selected": len(items), "objective_scored": len(objective),
            "passed": sum(x.get("status") == "passed" for x in objective),
            "failed": sum(x.get("status") == "failed" for x in objective),
            "human_review": sum(x.get("status") == "needs_human_review" for x in items),
            "not_run": sum(str(x.get("status", "")).startswith("not_run") for x in items),
            "errors": sum(x.get("status") == "error" for x in items),
            "objective_accuracy": round(sum(x.get("status") == "passed" for x in objective) / len(objective), 4) if objective else None}
    objective = [x for x in results if x.get("score") is not None]
    latencies = [x["latency_ms"] for x in results if isinstance(x.get("latency_ms"), (int, float))]
    return {"benchmark_version": "1.0", "suite_valid": suite_status["valid"], "suite_size": suite_status["total"],
        "offset": offset, "model": model, "provider": "ollama_local", "base_url_host": base_url.split("//", 1)[-1].split("/", 1)[0].split(":", 1)[0],
        "selected": len(results), "objective_scored": len(objective),
        "objective_accuracy": round(sum(x.get("status") == "passed" for x in objective) / len(objective), 4) if objective else None,
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "category_summary": category_summary, "results": results,
        "limitations": ["Objective checks are not a general intelligence score.",
            "Coding tasks require human review; generated code is never executed.",
            "Image tasks need real image fixtures and a vision-capable adapter and are not run.",
            "Long-context tasks use synthetic records and test retrieval, not arbitrary long-document understanding."]}
