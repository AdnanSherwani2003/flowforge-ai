#!/usr/bin/env python3
"""Audit installed backend packages and npm lockfile, without altering app images."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    inventory_code = "import importlib.metadata as m,json;print(json.dumps([{'name':d.metadata['Name'],'version':d.version} for d in m.distributions()]))"
    installed = json.loads(subprocess.check_output(["docker", "compose", "exec", "-T", "backend",
        "python", "-c", inventory_code], cwd=ROOT, text=True))
    with tempfile.TemporaryDirectory(prefix="flowforge-audit-") as tmp:
        folder = Path(tmp)
        folder.chmod(0o700)
        (folder / "installed.txt").write_text("\n".join(x["name"] + "==" + x["version"] for x in installed) + "\n")
        scanner = """import subprocess,json,sys,os
os.environ['HOME']='/tmp'
subprocess.run([sys.executable,'-m','venv','/tmp/auditor'],check=True,capture_output=True)
subprocess.run(['/tmp/auditor/bin/pip','install','--upgrade','pip==26.2.2'],check=True,capture_output=True)
subprocess.run(['/tmp/auditor/bin/pip','install','pip-audit==2.10.1'],check=True,capture_output=True)
result=subprocess.run(['/tmp/auditor/bin/pip-audit','--disable-pip','--no-deps','-r','/evidence/installed.txt','--format=json','-o','/evidence/python.json'],capture_output=True,text=True)
assert result.returncode in (0,1) and os.path.isfile('/evidence/python.json'), 'Audit failed; no clean result claimed'
"""
        (folder / "scanner.py").write_text(scanner)
        result = subprocess.run(["docker", "run", "--rm", "--user", "1000:1000", "-e", "HOME=/tmp",
            "--mount", f"type=bind,src={folder},dst=/evidence", "python:3.12-slim", "python", "/evidence/scanner.py"],
            cwd=ROOT, capture_output=True, text=True, timeout=300)
        assert result.returncode == 0, "Isolated Python scanner failed"
        data = json.loads((folder / "python.json").read_text())
    (ROOT / "docs/evaluation/implementation-09-python-audit.json").write_text(json.dumps(data, indent=2) + "\n")
    env = os.environ.copy()
    candidates = sorted((Path.home() / ".nvm/versions/node").glob("*/bin"))
    if candidates:
        env["PATH"] = str(candidates[-1]) + ":" + env["PATH"]
    env["NEXT_TELEMETRY_DISABLED"] = "1"
    result = subprocess.run(["npm", "audit", "--json"], cwd=ROOT / "frontend", env=env,
                            capture_output=True, text=True, timeout=120)
    npm = json.loads(result.stdout)
    assert result.returncode in (0,1) and "metadata" in npm, "npm audit failed"
    (ROOT / "docs/evaluation/implementation-09-npm-audit.json").write_text(json.dumps(npm, indent=2) + "\n")
    findings = {(x["name"], v["id"]) for x in data["dependencies"] for v in x["vulns"]}
    print("Python unique advisory matches:", len(findings), sorted(findings))
    print("npm findings:", npm["metadata"]["vulnerabilities"]["total"])
    summary = {"scanner": "pip-audit 2.10.1 (isolated ephemeral auditor); npm audit",
               "installed_package_count": len(installed), "python_unique_advisories": len(findings),
               "python_raw_entries": sum(len(x["vulns"]) for x in data["dependencies"]),
               "npm_findings": npm["metadata"]["vulnerabilities"]["total"],
               "python_status": "findings remain" if findings else "no matches",
               "note": "Successful audit execution is not a vulnerability-free result"}
    (ROOT / "docs/evaluation/implementation-09-dependencies.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
