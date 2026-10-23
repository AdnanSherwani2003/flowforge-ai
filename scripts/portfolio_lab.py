#!/usr/bin/env python3
"""Opt-in isolated Compose lab. Never reads the normal .env or targets its project."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shlex
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = Path.home() / ".local/share/flowforge-ai/portfolio-lab"


def private_write(path, text):
    with path.open("w") as handle:
        os.chmod(path, 0o600)
        handle.write(text)


def load_state(folder):
    folder = folder.expanduser().resolve()
    assert folder != ROOT and ROOT not in folder.parents, "Keep lab credentials outside Git"
    state = json.loads((folder / "state.json").read_text())
    assert state["project"].startswith("ff-portfolio-") and state["owner"] == "flowforge-portfolio-v1"
    return folder, state


def compose(folder, state, *args, input=None, check=True):
    cmd = ["docker", "compose", "-p", state["project"], "--env-file", str(folder / "lab.env"),
           "-f", str(ROOT / "compose.yaml"), "-f", str(folder / "override.yaml"), *args]
    result = subprocess.run(cmd, cwd=ROOT, input=input, capture_output=True, text=True, timeout=600)
    if result.returncode and check:
        # Detailed output can include test credentials: keep it private, never echo.
        private_write(folder / "last-error.log", result.stdout + result.stderr)
        raise RuntimeError("Lab command failed; inspect protected last-error.log locally")
    return result


def http(url, body=None, headers=None, timeout=40):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
            value = json.loads(raw) if "application/json" in res.headers.get("Content-Type", "") else raw.decode()
            return res.status, value, res.headers
    except urllib.error.HTTPError as res:
        raw = res.read()
        try:
            value = json.loads(raw)
        except ValueError:
            value = raw.decode(errors="replace")
        return res.code, value, res.headers


def wait(url, seconds=150):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        try:
            if http(url, timeout=2)[0] == 200:
                return
        except (OSError, ValueError):
            pass
        time.sleep(.5)
    raise RuntimeError("Lab readiness deadline exceeded")


def owned(folder, state):
    ids = compose(folder, state, "ps", "-aq").stdout.split()
    if ids:
        rows = json.loads(subprocess.check_output(["docker", "inspect", *ids], text=True))
        assert all(x["Config"]["Labels"].get("flowforge.portfolio-lab") == state["project"] for x in rows), "Ownership mismatch"
    volumes = set(subprocess.check_output(["docker", "volume", "ls", "-q"], text=True).split())
    for suffix in ("postgres_data", "n8n_data"):
        name = state["project"] + "_" + suffix
        if name in volumes:
            volume = json.loads(subprocess.check_output(["docker", "volume", "inspect", name], text=True))[0]
            assert volume.get("Labels", {}).get("flowforge.portfolio-lab") == state["project"], "Volume ownership mismatch"
    return ids


def start(args):
    folder = args.state.expanduser().resolve()
    assert folder != ROOT and ROOT not in folder.parents, "Keep lab credentials outside Git"
    if (folder / "state.json").exists():
        folder, state = load_state(folder)
        owned(folder, state)
        assert state.get("provisioned"), "Partial lab retained; inspect its private error log, stop it, then use a new state directory"
        compose(folder, state, "up", "-d", "--no-build", "--pull", "never")
        wait(state["backend"] + "/ready")
        wait(state["frontend"] + "/login")
        wait(state["n8n"] + "/healthz/readiness")
        print("Existing isolated lab resumed; no imports or configuration changes.")
        return
    assert not folder.exists(), "Use a new empty state path; existing files are never overwritten"
    for port in (args.backend_port, args.frontend_port, args.n8n_port):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", port))
    assert len({args.backend_port, args.frontend_port, args.n8n_port}) == 3
    folder.mkdir(parents=True, mode=0o700)
    project = "ff-portfolio-" + uuid.uuid4().hex[:10]
    state = {"owner": "flowforge-portfolio-v1", "project": project,
             "backend": "http://localhost:" + str(args.backend_port),
             "frontend": "http://localhost:" + str(args.frontend_port),
             "n8n": "http://localhost:" + str(args.n8n_port),
             "model_mode": "real-local" if args.real_model else "controlled-fixture",
             "username": "portfolio", "password": secrets.token_urlsafe(24)}
    state["provisioned"] = False
    private_write(folder / "state.json", json.dumps(state, indent=2) + "\n")
    values = {k: secrets.token_urlsafe(32) for k in ("POSTGRES_ADMIN_PASSWORD", "FLOWFORGE_DB_PASSWORD",
              "N8N_DB_PASSWORD", "N8N_ENCRYPTION_KEY", "FLOWFORGE_REVIEWER_SESSION_SECRET", "FLOWFORGE_DIGEST_SERVICE_KEY")}
    values.update({"GENERIC_TIMEZONE": "Asia/Kolkata", "FLOWFORGE_REVIEWER_USERNAME": state["username"],
                   "FLOWFORGE_REVIEWER_PASSWORD_HASH": "", "FLOWFORGE_ENABLE_SIMULATION": "false",
                   "OLLAMA_BASE_URL": "http://host.docker.internal:11434" if args.real_model else "http://ollama:11434"})
    def save_env():
        private_write(folder / "lab.env", "".join(k + "='" + v + "'\n" for k, v in values.items()))
    save_env()
    labels = {"flowforge.portfolio-lab": project}
    services = {s: {"labels": labels} for s in ("postgres", "backend", "frontend", "n8n")}
    services["frontend"]["environment"] = {"DASHBOARD_ORIGIN": state["frontend"]}
    services["n8n"]["environment"] = {"N8N_EDITOR_BASE_URL": state["n8n"] + "/",
        "WEBHOOK_URL": state["n8n"] + "/", "N8N_USE_WORKFLOW_PUBLICATION_SERVICE": "false"}
    if not args.real_model:
        services["ollama"] = {"image": project + "-backend", "labels": labels,
            "command": ["python", "/portfolio/portfolio_model_fixture.py"],
            "volumes": [str(ROOT / "scripts") + ":/portfolio:ro"]}
    # Compose !override replaces host ports instead of appending the normal bindings.
    text = "services:\n"
    for name, spec in services.items():
        text += "  " + name + ":\n"
        if name in {"backend", "frontend", "n8n"}:
            outer, inner = {"backend": (args.backend_port, 8001), "frontend": (args.frontend_port, 3000), "n8n": (args.n8n_port, 5678)}[name]
            text += '    ports: !override ["127.0.0.1:' + str(outer) + ":" + str(inner) + '"]\n'
        for key, value in spec.items():
            text += "    " + key + ": " + json.dumps(value) + "\n"
    text += "volumes:\n  postgres_data:\n    labels: " + json.dumps(labels) + "\n  n8n_data:\n    labels: " + json.dumps(labels) + "\n"
    private_write(folder / "override.yaml", text)
    # Do not silently attach preexisting resources even in the reserved project namespace.
    collision = subprocess.check_output(["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + project], text=True).strip()
    assert not collision, "Project collision"
    existing_volumes = set(subprocess.check_output(["docker", "volume", "ls", "-q"], text=True).split())
    assert not existing_volumes.intersection({project + "_postgres_data", project + "_n8n_data"}), "Volume collision"
    compose(folder, state, "config", "--quiet")
    compose(folder, state, "build", "backend", "frontend")
    code = "import sys;from pwdlib import PasswordHash;print(PasswordHash.recommended().hash(sys.stdin.read()))"
    encoded = compose(folder, state, "run", "--rm", "--no-deps", "-T", "backend", "python", "-c", code, input=state["password"]).stdout.strip()
    assert encoded.startswith("$argon2")
    values["FLOWFORGE_REVIEWER_PASSWORD_HASH"] = encoded
    save_env()
    compose(folder, state, "up", "-d", "postgres", "--pull", "never")
    for _ in range(150):
        final = compose(folder, state, "exec", "-T", "postgres", "cat", "/proc/1/comm", check=False).stdout.strip() == "postgres"
        probe = compose(folder, state, "exec", "-T", "postgres", "pg_isready", "-U", "flowforge_admin", check=False)
        if final and probe.returncode == 0:
            break
        time.sleep(.3)
    else:
        raise RuntimeError("New isolated PostgreSQL did not initialize")
    compose(folder, state, "run", "--rm", "--no-deps", "-T", "backend", "alembic", "upgrade", "head")
    definitions = [json.loads((ROOT / "workflows" / f).read_text()) for f in
                   ("support_ticket_intake.json", "lead_intake.json", "daily_operations_digest.json")]
    credential = [{"id": "FlowForgeDigestApi01", "name": "FlowForge Digest Service", "type": "httpHeaderAuth",
                   "data": {"name": "X-FlowForge-Digest-Key", "value": values["FLOWFORGE_DIGEST_SERVICE_KEY"]}}]
    # One-off CLI owns only this new project's database. Files travel by stdin, not argv.
    for name, content in [("workflows", definitions), ("credentials", credential)]:
        target = "/tmp/portfolio-" + name + ".json"
        js = "const fs=require('fs');fs.writeFileSync(process.argv[1],fs.readFileSync(0),{mode:0o600});"
        command = "node -e " + shlex.quote(js) + " " + target + " && n8n import:" + ("workflow" if name == "workflows" else "credentials") + " --input=" + target
        compose(folder, state, "run", "--rm", "--no-deps", "-T", "--entrypoint", "/bin/sh", "n8n", "-c", command, input=json.dumps(content))
    for workflow in ("FlowForgeSupportIntake01", "FlowForgeLeadIntake01", "FlowForgeDailyDigest01"):
        compose(folder, state, "run", "--rm", "--no-deps", "-T", "n8n", "publish:workflow", "--id=" + workflow)
    state["provisioned"] = True
    private_write(folder / "state.json", json.dumps(state, indent=2) + "\n")
    compose(folder, state, "up", "-d", "--no-build", "--pull", "never")
    wait(state["backend"] + "/ready")
    wait(state["frontend"] + "/login")
    wait(state["n8n"] + "/healthz/readiness")
    owned(folder, state)
    print("Isolated lab ready:", state["project"], state["backend"], state["frontend"], state["n8n"])
    print("Model mode:", state["model_mode"], "; private login details retained in state.json, not printed.")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["start", "status", "stop"])
    p.add_argument("--state", type=Path, default=DEFAULT_STATE)
    p.add_argument("--backend-port", type=int, default=18001)
    p.add_argument("--frontend-port", type=int, default=13000)
    p.add_argument("--n8n-port", type=int, default=15679)
    p.add_argument("--real-model", action="store_true", help="Use existing local Ollama; never download a model")
    args = p.parse_args()
    if args.action == "start":
        start(args); return
    folder, state = load_state(args.state)
    owned(folder, state)
    if args.action == "stop":
        compose(folder, state, "stop")
        print("Only this owned lab stopped. Volumes, records and private configuration retained.")
    else:
        print(json.dumps({k: state[k] for k in ["project", "backend", "frontend", "n8n", "model_mode"]}))
        print(compose(folder, state, "ps").stdout)


if __name__ == "__main__":
    main()
