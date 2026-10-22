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
    assert sql("flowforge_n8n",
               """SELECT "workflowId" FROM webhook_entity WHERE method='POST' AND "webhookPath"='support-ticket-intake'""") == "FlowForgeSupportIntake01"
    assert sql("flowforge_n8n", """SELECT count(*) FROM workflow_entity
        WHERE id='wWjX3Bi5uRDyLzGu' AND active=false AND "activeVersionId" IS NULL""") == "1"
    assert sql("flowforge", "SELECT version_num FROM alembic_version") == "005_reviews"
    assert sql("flowforge", """SELECT count(*) FROM information_schema.columns WHERE table_schema='public'
        AND table_name='workflow_runs' AND column_name IN ('execution_id','correlation_id') AND character_maximum_length=100""") == "2"
    assert sql("flowforge", """SELECT count(*) FROM pg_constraint WHERE conrelid='workflow_runs'::regclass
        AND conname='uq_workflow_runs_workflow_execution'""") == "1"
    print("PASS: Compose/runtime agree; failure simulation disabled; credential configuration agrees")
    print("PASS: 13 published nodes/connections/settings match version-controlled export")
    print("PASS: intended webhook owner, stale workflow unpublished, migration, trace column lengths and unique constraint")
    print("Published version:", actual["activeVersionId"])
    print("Workflow inventory (read only):")
    print(sql("flowforge_n8n", 'SELECT id,active FROM workflow_entity ORDER BY id'))


if __name__ == "__main__":
    main()
