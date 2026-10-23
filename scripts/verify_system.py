#!/usr/bin/env python3
"""Sequential final verification. Retains synthetic rows; no normal service outages."""
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    env = os.environ.copy()
    candidates = sorted((Path.home() / ".nvm/versions/node").glob("*/bin"))
    if candidates:
        env["PATH"] = str(candidates[-1]) + ":" + env["PATH"]
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    for command in (["npm", "test"], ["npm", "run", "lint"], ["npm", "run", "typecheck"], ["npm", "run", "build"]):
        subprocess.run(command, cwd=ROOT / "frontend", env=env, check=True)
    for command in (
        ["python3", "scripts/test_resilience_regressions.py", "--milestone", "9", "--backend-count", "233"],
        ["python3", "scripts/test_recovery_stack.py", "--output", "docs/evaluation/implementation-09-recovery.json"],
        ["python3", "scripts/test_security_system.py"],
        ["python3", "scripts/verify_workflow_runtime.py"],
        ["python3", "scripts/verify_backup_restore.py"],
    ):
        subprocess.run(command, cwd=ROOT, env=env, check=True)
    print("Final system verification completed; dependency findings are reported separately.", flush=True)


if __name__ == "__main__":
    main()
