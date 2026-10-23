#!/usr/bin/env python3
"""Protected application backup + isolated restore; never overwrite normal data."""
import collections
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def main():
    tag = "ff-restore-" + uuid.uuid4().hex[:12]
    protected = Path.home() / ".local/share/flowforge-ai/backups" / (
        "implementation-09-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6])
    protected.mkdir(mode=0o700)
    backup = protected / "flowforge.dump"
    def docker(*args, binary=False, **kw):
        return subprocess.run(["docker", *args], cwd=ROOT, check=True, capture_output=True,
                              text=not binary, timeout=180, **kw).stdout
    def original(query):
        return docker("compose", "exec", "-T", "postgres", "psql", "-U", "flowforge_admin",
                      "-d", "flowforge", "-Atc", query).strip()
    tables = original("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename!='alembic_version' ORDER BY tablename").splitlines()
    before = {}
    for table in tables:
        before[table] = collections.Counter(original('SELECT md5(to_jsonb(t)::text) FROM "' + table + '" t').splitlines())
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as handle:
        result = subprocess.run(["docker", "compose", "exec", "-T", "postgres", "pg_dump",
                                 "-U", "flowforge_admin", "-d", "flowforge", "-Fc"],
                                cwd=ROOT, stdout=handle, stderr=subprocess.PIPE, timeout=180)
        assert result.returncode == 0 and backup.stat().st_size > 0, "Application dump failed"
    docker("run", "--rm", "-d", "--name", tag, "--label", "flowforge.restore-test=" + tag,
           "--network", "none", "--tmpfs", "/var/lib/postgresql/data:rw,mode=700",
           "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:17-alpine")
    try:
        ready = False
        for _ in range(150):
            process = docker("exec", tag, "cat", "/proc/1/comm").strip()
            if process == "postgres":
                p = subprocess.run(["docker", "exec", tag, "pg_isready", "-U", "postgres"],
                                   capture_output=True, timeout=10)
                if p.returncode == 0:
                    ready = True; break
            time.sleep(.2)
        assert ready, "Disposable final PostgreSQL process not ready"
        docker("exec", tag, "createdb", "-U", "postgres", "restored")
        catalog = docker("exec", "-i", tag, "pg_restore", "--list", binary=True, input=backup.read_bytes())
        (protected / "catalog.txt").write_bytes(catalog)
        (protected / "catalog.txt").chmod(0o600)
        docker("exec", "-i", tag, "pg_restore", "--exit-on-error", "--no-owner", "--no-privileges",
               "-U", "postgres", "-d", "restored", binary=True, input=backup.read_bytes())
        def restored(query):
            return docker("exec", tag, "psql", "-U", "postgres", "-d", "restored", "-Atc", query).strip()
        counts = {}
        for table in tables:
            actual = collections.Counter(restored('SELECT md5(to_jsonb(t)::text) FROM "' + table + '" t').splitlines())
            assert actual == before[table], "Restore row values differ: " + table
            counts[table] = sum(actual.values())
        assert restored("SELECT version_num FROM alembic_version") == "007_daily_digests"
        code = """from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    assert client.get('/ready').status_code == 200
    result=client.get('/api/tickets')
    assert result.status_code == 200 and result.json()['total'] > 0
print('restored_api_read_passed')
"""
        output = docker("run", "--rm", "--network", "container:" + tag,
                        "-e", "DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/restored",
                        "flowforge-ai-backend", "python", "-c", code)
        assert "restored_api_read_passed" in output
        for table in tables:
            after = collections.Counter(original('SELECT md5(to_jsonb(t)::text) FROM "' + table + '" t').splitlines())
            assert after == before[table], "Normal application changed during backup drill"
        report = {"passed": len(tables) + 4, "failed": 0, "skipped": 0,
                  "restored_table_counts": counts, "migration": "007_daily_digests",
                  "api_readiness_and_ticket_read": "passed", "normal_application_unchanged": True,
                  "backup_file": str(backup), "backup_mode": "0600", "directory_mode": "0700",
                  "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
                  "target": "Disposable network=none PostgreSQL 17 with tmpfs; no production mounts",
                  "limitations": ["Ownership/ACL restoration not tested (--no-owner --no-privileges)",
                                 "No normal database restore, reboot, host-loss recovery-time/RPO guarantee",
                                 "No n8n database or volume restore performed"]}
        (ROOT / "docs/evaluation/implementation-09-restore.json").write_text(json.dumps(report, indent=2) + "\n")
        print("Isolated application restore:", report["passed"], "passed, 0 failed, 0 skipped", flush=True)
        print("Protected backup retained:", backup, flush=True)
    finally:
        info = json.loads(docker("inspect", tag))[0]
        assert info["Config"]["Labels"].get("flowforge.restore-test") == tag
        subprocess.run(["docker", "stop", "--time", "5", tag], capture_output=True, timeout=30, check=True)


if __name__ == "__main__":
    main()
