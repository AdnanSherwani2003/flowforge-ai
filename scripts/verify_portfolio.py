#!/usr/bin/env python3
"""Run fresh Implementation 10 checks sequentially, preserving historic reports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from portfolio_lab import ROOT, DEFAULT_STATE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--skip-recovery", action="store_true")
    args = parser.parse_args()
    env = os.environ.copy()
    bins = sorted((Path.home() / ".nvm/versions/node").glob("*/bin"))
    if bins:
        env["PATH"] = str(bins[-1]) + ":" + env["PATH"]
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    logs = Path.home() / ".local/share/flowforge-ai/verification-10"
    logs.mkdir(mode=0o700, exist_ok=True)
    commands = [(n, ["npm", *c], ROOT / "frontend") for n, c in [
        ("frontend-tests", ["test"]), ("lint", ["run", "lint"]),
        ("types", ["run", "typecheck"]), ("build", ["run", "build"])]]
    commands += [
        ("regressions", ["python3", "scripts/test_resilience_regressions.py", "--milestone", "10", "--backend-count", "233"], ROOT),
        ("workflow-parity", ["python3", "scripts/verify_workflow_runtime.py"], ROOT),
        ("portfolio-benchmark", ["python3", "scripts/benchmark_portfolio.py", "--state", str(args.state)], ROOT)]
    if not args.skip_recovery:
        commands.append(("recovery", ["python3", "scripts/test_recovery_stack.py", "--output",
                                      "docs/evaluation/implementation-10-recovery.json"], ROOT))
    commands.append(("secrets", ["python3", "scripts/audit_secrets.py", "--output",
                                 "docs/evaluation/implementation-10-secrets.json"], ROOT))
    report = {"checks": [], "recovery_explicitly_omitted": args.skip_recovery,
              "benchmark_model_mode": "See benchmark JSON; controlled fixture is not real inference"}
    target = ROOT / "docs/evaluation/implementation-10-verification.json"
    for name, command, cwd in commands:
        print("RUN", name, flush=True)
        result = subprocess.run(command, cwd=cwd, env=env, text=True, capture_output=True, timeout=900)
        path = logs / (name + ".log")
        with path.open("w") as handle:
            path.chmod(0o600)
            handle.write(result.stdout + result.stderr)
        report["checks"].append({"name": name, "command": command, "exit_code": result.returncode,
                                "log_path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        target.write_text(json.dumps(report, indent=2) + "\n")
        assert result.returncode == 0, name + " failed; inspect private log"
        print("PASS", name, flush=True)
    print("Fresh portfolio verification completed. No historical pass was reused.", flush=True)


if __name__ == "__main__":
    main()
