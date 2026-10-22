#!/usr/bin/env python3
"""Genuine inference over synthetic labels; no customer database access.
Run in backend image with /workspace read-only mounted and PYTHONPATH=/app.
"""
import argparse
import asyncio
from dataclasses import asdict
import json
import statistics
from pathlib import Path
from app.core.config import settings
from app.schemas.enrichment import PROMPT_VERSION, SCHEMA_VERSION
from app.services.ollama_client import classify_ticket


async def evaluate(fixtures):
    rows = []
    for case in fixtures:
        result = await classify_ticket(case["subject"], case["body"])
        row = {"id": case["id"], "expected_category": case["category"],
               "expected_priority": case["priority"], **asdict(result)}
        rows.append(row)
    count = len(rows)
    inferred = [r for r in rows if r["diagnostic_code"] not in ("suspicious_input", "input_too_long")]
    return {
        "model": settings.OLLAMA_MODEL, "digest": settings.OLLAMA_MODEL_DIGEST,
        "prompt_version": PROMPT_VERSION, "schema_version": SCHEMA_VERSION,
        "num_gpu": settings.OLLAMA_NUM_GPU, "synthetic_only": True,
        "count": count, "model_call_cases": len(inferred),
        "category_correct": sum(r["category"] == r["expected_category"] for r in rows),
        "priority_correct": sum(r["priority"] == r["expected_priority"] for r in rows),
        "model_category_correct": sum(r["category"] == r["expected_category"] for r in inferred),
        "model_priority_correct": sum(r["priority"] == r["expected_priority"] for r in inferred),
        "abstentions": sum(r["status"] == "needs_review" for r in rows),
        "invalid_outputs": sum(r["diagnostic_code"] == "invalid_output" for r in rows),
        "unavailable": sum(r["status"] == "unavailable" for r in rows),
        "latency_ms": {"first": rows[0]["duration_ms"],
                       "median": statistics.median(r["duration_ms"] for r in inferred),
                       "max": max(r["duration_ms"] for r in inferred)},
        "results": rows,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", default="/workspace/backend/tests/fixtures/enrichment_eval.json")
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    if args.cpu:
        settings.OLLAMA_NUM_GPU = 0
    print(json.dumps(asyncio.run(evaluate(json.loads(Path(args.fixtures).read_text()))), indent=2))
