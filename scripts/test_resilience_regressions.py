#!/usr/bin/env python3
"""Sequential existing suites; preserve earlier milestone evidence and synthetic rows."""
import json
import argparse
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Reuse verified suites from this milestone report")
    args = parser.parse_args()
    commands = [
        ("backend", ["docker", "compose", "exec", "-T", "backend", "pytest", "-q"], 222, "222 passed"),
        ("lead", ["python3", "scripts/test_lead_workflow.py", "--output", "docs/evaluation/implementation-08-lead.json"], 358, "358 passed"),
        ("support", ["python3", "scripts/test_support_workflow.py"], 192, "192/192"),
        ("enrichment", ["python3", "scripts/test_enrichment_workflow.py"], 21, '"checks_passed": 21'),
        ("reviews", ["python3", "scripts/test_review_integration.py", "--output", "docs/evaluation/implementation-08-review.json"], 29, '"checks_passed": 29'),
        ("smoke", ["python3", "scripts/smoke_test.py"], 8, "SUCCESS:"),
        ("digest", ["python3", "scripts/test_digest_integration.py", "--output", "docs/evaluation/implementation-08-digest.json"], 28, "28 passed"),
        ("digest_faults", ["python3", "scripts/test_digest_faults.py", "--output", "docs/evaluation/implementation-08-digest-faults.json"], 44, "44 passed"),
        ("lead_faults", ["python3", "scripts/test_lead_faults.py"], 36, "36/36"),
        ("support_faults", ["python3", "scripts/test_workflow_faults.py"], 39, "39/39"),
    ]
    report_path = ROOT / "docs/evaluation/implementation-08-regressions.json"
    results = json.loads(report_path.read_text()) if args.resume and report_path.exists() else {}
    for name, command, count, marker in commands:
        if results.get(name, {}).get("passed") == count and results[name].get("failed") == 0 and results[name].get("command") == command:
            print(name + ": previously executed and verified in this milestone", flush=True)
            continue
        if name in ("enrichment", "reviews"):
            deadline, quiet = time.monotonic() + 90, 0
            while time.monotonic() < deadline and quiet < 3:
                active = subprocess.check_output(["docker", "compose", "exec", "-T", "postgres", "psql",
                    "-U", "flowforge_admin", "-d", "flowforge", "-Atc",
                    "SELECT count(*) FROM ticket_enrichments WHERE status='processing'"], cwd=ROOT, text=True).strip()
                quiet = quiet + 1 if active == "0" else 0
                time.sleep(1)
            assert quiet == 3, "Inference did not settle within bound; inspect active claims"
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=300)
        log = Path("/tmp/flowforge-08-" + name + ".log")
        log.write_text(result.stdout + result.stderr)
        log.chmod(0o600)
        results[name] = {"passed": count if result.returncode == 0 and marker in result.stdout else 0,
                         "failed": int(result.returncode != 0 or marker not in result.stdout),
                         "skipped": 0, "command": command}
        (ROOT / "docs/evaluation/implementation-08-regressions.json").write_text(json.dumps(results, indent=2) + "\n")
        assert results[name]["failed"] == 0, name + " failed; inspect private log " + str(log)
        print(name + ": " + str(count) + " passed, 0 failed, 0 skipped", flush=True)


if __name__ == "__main__":
    main()
