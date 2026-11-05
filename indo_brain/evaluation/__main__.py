"""Run Indo's opt-in local benchmark: python -m indo_brain.evaluation --limit 10"""
from __future__ import annotations
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .runner import run_local_benchmark
from .suite import validate_suite


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Indo's local Ollama intelligence benchmark.")
    parser.add_argument("--limit", type=int, default=10, help="Cases per run (1-140).")
    parser.add_argument("--offset", type=int, default=0, help="Start index in the selected category list (0-based).")
    parser.add_argument("--categories", default="", help="Comma-separated category names.")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("INDO_OLLAMA_TIMEOUT", "120")))
    parser.add_argument("--base-url", default=os.getenv("INDO_OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--model", default=os.getenv("INDO_OLLAMA_MODEL", "qwen2.5:3b"))
    parser.add_argument("--output", default="", help="Optional report JSON path.")
    args = parser.parse_args()
    if not validate_suite()["valid"]:
        parser.error("Benchmark suite manifest failed validation.")
    categories = [x.strip() for x in args.categories.split(",") if x.strip()] or None
    report = run_local_benchmark(base_url=args.base_url, model=args.model, limit=args.limit, offset=args.offset,
                                 categories=categories, timeout=args.timeout)
    target = Path(args.output) if args.output else Path(f"indo_benchmark_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json")
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("benchmark_version", "suite_size", "model", "selected", "objective_scored", "objective_accuracy", "mean_latency_ms", "category_summary")}, indent=2))
    print(f"Full report: {target.resolve()}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
