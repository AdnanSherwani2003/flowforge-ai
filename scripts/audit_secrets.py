#!/usr/bin/env python3
"""Redacted checks of working files and reachable Git history; never print values."""
import argparse
import base64
import json
from pathlib import Path
import re
import subprocess
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/evaluation/implementation-09-secrets.json")
    args = parser.parse_args()
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    sources = [ROOT / ".env"]
    backups = Path.home() / ".local/share/flowforge-ai/backups"
    sources += [p for p in backups.rglob("*") if p.is_file() and
                (".env" in p.name or p.name.startswith("env."))]
    values = set()
    short = 0
    for path in sources:
        for line in path.read_text(errors="ignore").splitlines():
            key, sep, value = line.partition("=")
            if sep and any(x in key.upper() for x in ("PASSWORD", "SECRET", "ENCRYPTION_KEY", "SERVICE_KEY")):
                value = value.strip().strip("'\\\"")
                if len(value) >= 12:
                    values.add(value)
                elif value:
                    short += 1
    variants = set()
    for value in values:
        variants.update((value.encode(), base64.b64encode(value.encode()),
                         base64.urlsafe_b64encode(value.encode()), value.encode().hex().encode(),
                         urllib.parse.quote(value, safe="").encode()))
    patterns = [rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                rb"gh[pousr]_[A-Za-z0-9]{36}", rb"github_pat_[A-Za-z0-9_]{70,}",
                rb"sk-proj-[A-Za-z0-9_-]{40,}", rb"AKIA[0-9A-Z]{16}"]
    files = sorted(set(git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()))
    hits = []
    def match(data):
        return any(v in data for v in variants) or any(re.search(p, data) for p in patterns)
    for name in files:
        if match((ROOT / name).read_bytes()):
            hits.append({"scope": "working tree", "path": name})
    objects = [x.split()[0] for x in git("rev-list", "--objects", "--all").splitlines()]
    types = subprocess.check_output(["git", "cat-file", "--batch-check=%(objectname) %(objecttype)"],
        cwd=ROOT, input=("\n".join(objects) + "\n").encode()).decode().splitlines()
    blobs = [x.split()[0] for x in types if x.endswith(" blob")]
    for sha in blobs:
        if match(subprocess.check_output(["git", "cat-file", "blob", sha], cwd=ROOT)):
            hits.append({"scope": "reachable history", "blob": sha})
    report = {"working_tree_files_scanned": len(files), "reachable_git_blobs_scanned": len(blobs),
              "protected_config_sources_compared": len(sources), "matches": len(hits), "findings": hits,
              "short_secret_settings_for_manual_review": short,
              "env_ignored": subprocess.run(["git", "check-ignore", ".env"], cwd=ROOT, capture_output=True).returncode == 0,
              "env_mode": oct((ROOT / ".env").stat().st_mode & 0o777),
              "limitations": ["Known current/retained rollback values and encodings plus high-confidence key/token patterns",
                             "Not exhaustive detection of every arbitrary historical secret; manual source/export review also required"]}
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    assert not hits, "Potential secret exposure: inspect the redacted report before any credential action"


if __name__ == "__main__":
    main()
