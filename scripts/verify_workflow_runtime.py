#!/usr/bin/env python3
"""Read-only verification of scoped FlowForge runtime and supported workflow export."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True)


def sql(database, statement):
    return run("docker", "compose", "exec", "-T", "postgres", "psql",
               "-U", "flowforge_admin", "-d", database, "-At", "-c", statement).strip()


def main():
    cfg = json.loads(run("docker", "compose", "config", "--format", "json"))
    assert cfg["services"]["backend"]["environment"]["ENABLE_FAILURE_SIMULATION"] == "false"
    for service in ("backend", "n8n"):
        instance = json.loads(run("docker", "inspect", f"flowforge-ai-{service}-1"))[0]
        actual = dict(entry.split("=", 1) for entry in instance["Config"]["Env"] if "=" in entry)
        expected = cfg["services"][service]["environment"]
        keys = ["ENABLE_FAILURE_SIMULATION", "ENRICHMENT_ENABLED", "OLLAMA_BASE_URL",
                "OLLAMA_MODEL", "OLLAMA_MODEL_DIGEST", "OLLAMA_TIMEOUT_SECONDS", "OLLAMA_NUM_GPU"] if service == "backend" else [
            "DB_POSTGRESDB_PASSWORD", "N8N_ENCRYPTION_KEY",
            "EXECUTIONS_DATA_SAVE_ON_SUCCESS", "EXECUTIONS_DATA_SAVE_ON_ERROR",
            "EXECUTIONS_DATA_SAVE_ON_PROGRESS", "EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS",
            "EXECUTIONS_DATA_PRUNE",
        ]
        assert all(actual.get(key) == str(expected[key]) for key in keys), service + " configuration mismatch"
    run("docker", "compose", "exec", "-T", "backend", "python", "-c",
        "from app.core.config import settings; assert settings.ENABLE_FAILURE_SIMULATION is False")
    run("docker", "compose", "exec", "-T", "n8n", "n8n", "export:workflow",
        "--id=FlowForgeSupportIntake01", "--published", "--output=/tmp/flowforge-verification.json")
    actual = json.loads(run("docker", "compose", "exec", "-T", "n8n", "cat", "/tmp/flowforge-verification.json"))[0]
    expected = json.loads((ROOT / "workflows/support_ticket_intake.json").read_text())
    assert all(actual[key] == expected[key] for key in expected), "Published workflow differs from source"
    assert actual["active"] and actual["activeVersionId"] == actual["versionId"]
    assert len(actual["nodes"]) == 13
    run("docker", "compose", "exec", "-T", "n8n", "n8n", "export:workflow",
        "--id=FlowForgeLeadIntake01", "--published", "--output=/tmp/flowforge-lead-verification.json")
    lead_actual = json.loads(run("docker", "compose", "exec", "-T", "n8n", "cat", "/tmp/flowforge-lead-verification.json"))[0]
    lead_expected = json.loads((ROOT / "workflows/lead_intake.json").read_text())
    assert all(lead_actual[key] == lead_expected[key] for key in lead_expected), "Published lead workflow differs"
    assert lead_actual["active"] and lead_actual["activeVersionId"] == lead_actual["versionId"]
    assert len(lead_actual["nodes"]) == 11
    print("PASS: 11 published lead nodes/connections/settings match source; separate webhook owner")
    run("docker", "compose", "exec", "-T", "n8n", "n8n", "export:workflow",
        "--id=FlowForgeDailyDigest01", "--published", "--output=/tmp/flowforge-digest-verification.json")
    digest_actual = json.loads(run("docker", "compose", "exec", "-T", "n8n", "cat", "/tmp/flowforge-digest-verification.json"))[0]
    digest_expected = json.loads((ROOT / "workflows/daily_operations_digest.json").read_text())
    assert all(digest_actual[key] == digest_expected[key] for key in digest_expected), "Published digest workflow differs"
    assert digest_actual["active"] and digest_actual["activeVersionId"] == digest_actual["versionId"]
    assert len(digest_actual["nodes"]) == 5 and digest_actual["settings"]["timezone"] == "Asia/Kolkata"
    assert json.loads((ROOT / "backend/tests/fixtures/daily_operations_digest.json").read_text()) == digest_expected
    run("docker", "compose", "exec", "-T", "n8n", "n8n", "export:workflow", "--all", "--output=/tmp/flowforge-inventory.json")
    inventory = json.loads(run("docker", "compose", "exec", "-T", "n8n", "cat", "/tmp/flowforge-inventory.json"))
    for path, owner in (("support-ticket-intake", "FlowForgeSupportIntake01"), ("lead-intake", "FlowForgeLeadIntake01")):
        owners = [w["id"] for w in inventory if w["active"] and any(n["type"] == "n8n-nodes-base.webhook" and n["parameters"].get("path") == path for n in w["nodes"])]
        assert owners == [owner], "Conflicting active webhook definition"
    assert next(w for w in inventory if w["id"] == "wWjX3Bi5uRDyLzGu")["active"] is False
    assert sum(w["id"] == "FlowForgeDailyDigest01" for w in inventory) == 1
    print("PASS: five published digest nodes match source; 09:00 calendar schedule and timezone verified")
    assert sql("flowforge", "SELECT version_num FROM alembic_version") == "007_daily_digests"
    assert sql("flowforge", """SELECT count(*) FROM information_schema.columns WHERE table_schema='public'
        AND table_name='workflow_runs' AND column_name IN ('execution_id','correlation_id') AND character_maximum_length=100""") == "2"
    assert sql("flowforge", """SELECT count(*) FROM pg_constraint WHERE conrelid='workflow_runs'::regclass
        AND conname='uq_workflow_runs_workflow_execution'""") == "1"
    print("PASS: Compose/runtime agree; failure simulation disabled; credential configuration agrees")
    print("PASS: 13 published nodes/connections/settings match version-controlled export")
    print("PASS: intended webhook owner, stale workflow unpublished, migration, trace column lengths and unique constraint")
    print("Published version:", actual["activeVersionId"])
    print("Workflow inventory (read only):")
    print(json.dumps([{"id":w["id"],"active":w["active"]} for w in inventory]))


if __name__ == "__main__":
    main()
