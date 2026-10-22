#!/usr/bin/env python3
"""Isolated n8n + synthetic TCP fault proxy; never enables normal backend hooks.

Requires the existing local images and FlowForge network. Creates no named volumes.
Only the two uniquely named test containers created here are stopped on exit.
Existing workflows and n8n tables are never modified by this harness.
"""
import copy
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from test_support_workflow import make_request, BACKEND_URL

ROOT = Path(__file__).resolve().parents[1]


def docker(*args, check=True):
    return subprocess.run(["docker", *args], cwd=ROOT, check=check, capture_output=True, text=True)


def main():
    tag = "ff-fault-" + uuid.uuid4().hex[:10]
    proxy, engine = tag + "-proxy", tag + "-n8n"
    network = json.loads(docker("inspect", "flowforge-ai-backend-1").stdout)[0]["NetworkSettings"]["Networks"]
    assert "flowforge-ai_default" in network, "Expected scoped FlowForge network"
    assert docker("compose", "exec", "-T", "backend", "python", "-c", "from app.core.config import settings; assert settings.ENABLE_FAILURE_SIMULATION is False").returncode == 0
    checks = 0
    started = []

    def check(condition, name):
        nonlocal checks
        assert condition, name
        checks += 1
        print("PASS:", name, flush=True)

    def host_port(container, port):
        info = json.loads(docker("inspect", container).stdout)[0]
        return int(info["NetworkSettings"]["Ports"][str(port) + "/tcp"][0]["HostPort"])

    def execution_data(response):
        # Read-only inspection of this disposable engine's synthetic history.
        execution = response["execution_id"].rsplit("-", 1)[-1]
        code = (
            "const {DatabaseSync}=require('node:sqlite');"
            "const db=new DatabaseSync('/home/node/.n8n/database.sqlite',{readOnly:true});"
            "const r=db.prepare('SELECT data FROM execution_data WHERE executionId=?').get(process.argv[1]);"
            "process.stdout.write(JSON.stringify(r||{}));db.close();"
        )
        for _ in range(40):
            value = json.loads(docker("exec", engine, "node", "-e", code, execution).stdout)
            if value.get("data"):
                return value["data"]
            time.sleep(0.1)
        raise AssertionError("Synthetic execution data not saved")

    with tempfile.TemporaryDirectory(prefix=tag + "-") as folder:
        folder = Path(folder)
        os.chmod(folder, 0o755)
        definition = copy.deepcopy(json.loads((ROOT / "workflows/support_ticket_intake.json").read_text()))
        definition["id"] = "IsolatedFaultIntake"
        definition["name"] = "Isolated synthetic transport verification"
        definition["settings"]["saveDataSuccessExecution"] = "all"
        definition["settings"]["saveDataErrorExecution"] = "all"
        for node in definition["nodes"]:
            if node["name"] == "Extract & Prepare":
                node["parameters"]["jsonOutput"] = node["parameters"]["jsonOutput"].replace(
                    "execution_id: String($execution.id)", f"execution_id: '{tag}-' + String($execution.id)"
                )
            if node["name"] == "Call FastAPI Backend":
                node["parameters"]["url"] = (
                    "={{ $json.payload.fault === 'refused' ? 'http://" + proxy +
                    ":8081/' : 'http://" + proxy + ":8080/' + $json.payload.fault }}"
                )
            if node["name"] == "Record Workflow Run":
                node["parameters"]["jsonBody"] = node["parameters"]["jsonBody"].replace(
                    "workflow_name: 'support_ticket_intake'", f"workflow_name: '{tag}'"
                )
                node["parameters"]["url"] = (
                    "={{ $('Extract & Prepare').item.json.payload.fault === 'telemetry-down' ? "
                    "'http://" + proxy + ":8080/telemetry-unavailable' : "
                    "'http://backend:8001/api/workflow-runs' }}"
                )
        (folder / "workflow.json").write_text(json.dumps(definition))
        (folder / "server.py").write_text((ROOT / "scripts/fault_proxy.py").read_text())
        try:
            docker(
                "run", "--rm", "-d", "--name", proxy, "--network", "flowforge-ai_default",
                "-p", "127.0.0.1::8080", "--mount", f"type=bind,src={folder},dst=/harness,readonly",
                "flowforge-ai-backend", "python", "/harness/server.py",
            )
            started.append(proxy)
            proxy_port = host_port(proxy, 8080)
            proxy_url = f"http://127.0.0.1:{proxy_port}"
            for _ in range(50):
                if make_request(proxy_url)[0] == 200:
                    break
                time.sleep(0.1)
            check(make_request(proxy_url)[0] == 200, "isolated proxy ready")
            # Probe inside Docker: host port forwarding may translate a reset to EOF.
            probe = (
                "import socket,errno; s=socket.create_connection(('127.0.0.1',8080),timeout=2);"
                r"s.sendall(b'POST /reset HTTP/1.1\r\nHost: synthetic\r\nContent-Length: 2\r\n\r\n{}');"
                "\ntry: s.recv(1024); raise AssertionError('Expected TCP RST')"
                "\nexcept OSError as e: assert e.errno==errno.ECONNRESET; print('ECONNRESET')"
                "\nfinally: s.close()"
            )
            check(docker("exec", proxy, "python", "-c", probe).stdout.strip() == "ECONNRESET",
                  "Linux TCP RST observed (ECONNRESET)")
            before_reset = make_request(proxy_url)[2]["reset"]
            docker(
                "run", "--rm", "-d", "--name", engine, "--network", "flowforge-ai_default",
                "-p", "127.0.0.1::5678",
                "--tmpfs", "/home/node/.n8n:uid=1000,gid=1000,mode=700",
                "--mount", f"type=bind,src={folder},dst=/harness,readonly",
                "-e", "N8N_DIAGNOSTICS_ENABLED=false", "-e", "N8N_SECURE_COOKIE=false",
                "-e", "EXECUTIONS_DATA_PRUNE=false",
                # CLI publish only sets activeVersionId in 2.43.8. Use supported
                # legacy startup registration in this disposable engine only.
                "-e", "N8N_USE_WORKFLOW_PUBLICATION_SERVICE=false",
                "--entrypoint", "/bin/sh",
                "n8nio/n8n:2.43.8", "-c",
                "n8n import:workflow --input=/harness/workflow.json && "
                "n8n publish:workflow --id=IsolatedFaultIntake && n8n start",
            )
            started.append(engine)
            webhook = f"http://127.0.0.1:{host_port(engine, 5678)}/webhook/support-ticket-intake"
            health = webhook.split("/webhook/")[0] + "/healthz/readiness"
            for _ in range(450):
                if make_request(health, timeout=1)[0] == 200:
                    break
                info = json.loads(docker("inspect", engine).stdout)[0]
                assert info["State"]["Running"], "Isolated n8n exited"
                time.sleep(0.2)
            check(make_request(health)[0] == 200, "disposable n8n ready with separate tmpfs SQLite")
            # Readiness precedes trigger registration in this version.
            for _ in range(150):
                code, _, ready = make_request(webhook, "POST", {"fault": "503"}, timeout=2)
                if code == 503 and ready.get("outcome") == "service_unavailable":
                    break
                time.sleep(0.2)
            check(code == 503 and ready.get("outcome") == "service_unavailable", "isolated webhook registered")
            docker("exec", engine, "n8n", "export:workflow", "--id=IsolatedFaultIntake", "--output=/tmp/roundtrip.json")
            imported = json.loads(docker("exec", engine, "cat", "/tmp/roundtrip.json").stdout)[0]
            check(imported["nodes"] == definition["nodes"] and imported["connections"] == definition["connections"],
                  "supported import/export round trip retains tested node definitions")
            for mode, expected_code in [
                ("503", None), ("refused", "ECONNREFUSED"), ("reset", "ECONNRESET"),
                ("timeout", "TIMEOUT"), ("after-persist", "TIMEOUT"),
            ]:
                payload = {
                    "source_event_id": tag + "-" + mode, "subject": "Synthetic transport fixture",
                    "body": "Synthetic only", "fault": mode,
                }
                before = make_request(BACKEND_URL + "/api/tickets?limit=1")[2]["total"]
                began = time.monotonic()
                status, _, response = make_request(webhook, "POST", payload, timeout=12)
                elapsed = time.monotonic() - began
                check(status == 503 and response.get("outcome") == "service_unavailable", mode + " maps to HTTP 503")
                check("SYNTHETIC_PRIVATE_ERROR_CANARY" not in json.dumps(response) and proxy not in json.dumps(response), mode + " sanitized")
                saved = execution_data(response)
                if expected_code == "TIMEOUT":
                    check(4.5 <= elapsed <= 8, mode + " bounded at five seconds")
                    check(any(code in saved for code in ("ETIMEDOUT", "ESOCKETTIMEDOUT", "ECONNABORTED")), mode + " n8n transport timeout recorded")
                elif expected_code:
                    check(expected_code in saved, mode + " n8n recorded " + expected_code)
                if mode == "reset":
                    check(make_request(proxy_url)[2]["reset"] == before_reset + 1, "n8n reached actual RST handler")
                after = make_request(BACKEND_URL + "/api/tickets?limit=1")[2]["total"]
                check(after - before == (1 if mode == "after-persist" else 0), mode + " persistence boundary")
                if mode in ("503", "after-persist"):
                    replay = {**payload, "fault": "success"}
                    status, _, result = make_request(webhook, "POST", replay)
                    expected = 200 if mode == "after-persist" else 201
                    check(status == expected, mode + " first retry")
                    ticket = result["ticket_id"]
                    status, _, result = make_request(webhook, "POST", replay)
                    check(status == 200 and result.get("duplicate") is True and result.get("ticket_id") == ticket, mode + " subsequent replay")
                    check(make_request(BACKEND_URL + "/api/tickets?limit=1")[2]["total"] == before + 1, mode + " exactly one business ticket")

            payload = {"source_event_id": tag + "-telemetry", "subject": "Synthetic", "body": "Synthetic", "fault": "telemetry-down"}
            status, _, response = make_request(webhook, "POST", payload)
            check(status == 201 and response.get("telemetry") == "best_effort", "telemetry outage preserves committed ticket response")
            execution_data(response)
            check(make_request(BACKEND_URL + "/api/workflow-runs/" + response["execution_id"])[0] == 404, "telemetry is explicitly best effort")
            check(make_request(proxy_url)[2].get("telemetry-unavailable") == 1, "telemetry outage reached proxy")
        except Exception:
            if engine in started:
                log = docker("logs", "--tail", "25", engine, check=False)
                print("Isolated engine diagnostics:", log.stdout, log.stderr)
            raise
        finally:
            for name in reversed(started):
                docker("stop", "--time", "10", name, check=False)
    print(f"Isolated transport verification: {checks}/{checks} assertions passed")


if __name__ == "__main__":
    main()
