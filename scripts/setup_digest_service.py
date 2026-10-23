#!/usr/bin/env python3
"""Provision one narrowly scoped credential; never print secret material.

Only targets this project's Compose n8n service. Existing credentials are never
overwritten. The public workflow export contains a credential reference only.
"""
import json
import os
import secrets
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
KEY="FLOWFORGE_DIGEST_SERVICE_KEY"
CREDENTIAL="FlowForgeDigestApi01"


def docker(*args,input=None,check=True):
    return subprocess.run(["docker","compose",*args],cwd=ROOT,input=input,capture_output=True,text=True,check=check)


def main():
    env=ROOT/".env"
    assert env.is_file() and env.stat().st_mode & 0o777 == 0o600, "Keep local configuration mode 0600"
    original=env.read_text()
    values={k:v.strip().strip("'\"") for line in original.splitlines() if "=" in line for k,v in [line.split("=",1)]}
    key=values.get(KEY)
    if not key:
        assert KEY not in values, "Refuse to replace an existing empty key; configure it privately first"
        key=secrets.token_urlsafe(48)
        with env.open("a") as handle:
            handle.write(("" if original.endswith("\n") else "\n")+KEY+"='"+key+"'\n")
        print("Created one scoped service key in ignored mode-0600 configuration.")
    assert len(key)>=32, "A strong existing digest key is required"
    credential_export="/tmp/flowforge-digest-credential-inventory.json"
    try:
        exported=docker("exec","-T","n8n","n8n","export:credentials","--all","--output="+credential_export,check=False)
        if exported.returncode:
            assert "No credentials found" in exported.stdout+exported.stderr, "Credential inventory failed"
            credentials=[]
        else:
            credentials=json.loads(docker("exec","-T","n8n","cat",credential_export).stdout)
        existing=next((c for c in credentials if c["id"]==CREDENTIAL),None)
        if existing:
            assert existing["name"]=="FlowForge Digest Service" and existing["type"]=="httpHeaderAuth", "Unexpected credential identity"
            print("Reusing the existing digest credential; no credentials changed.")
            return
        assert not any(c["name"]=="FlowForge Digest Service" for c in credentials), "Resolve an existing same-name credential before provisioning"
        docker("exec","-T","n8n","n8n","export:workflow","--id=FlowForgeLeadIntake01","--output=/tmp/flowforge-digest-owner.json")
        owner=json.loads(docker("exec","-T","n8n","cat","/tmp/flowforge-digest-owner.json").stdout)[0]
        project=next(s["projectId"] for s in owner["shared"] if s["role"]=="workflow:owner")
        credential=[{"id":CREDENTIAL,"name":"FlowForge Digest Service","type":"httpHeaderAuth",
                     "data":{"name":"X-FlowForge-Digest-Key","value":key}}]
        private_path="/tmp/flowforge-digest-private-import.json"
        try:
            docker("exec","-T","n8n","node","-e",
                   "const fs=require('fs');fs.writeFileSync(process.argv[1],fs.readFileSync(0),{mode:0o600,flag:'wx'});",
                   private_path,input=json.dumps(credential))
            result=docker("exec","-T","n8n","n8n","import:credentials","--input="+private_path,"--projectId="+project)
            assert "Successfully imported 1 credential" in result.stdout, "Credential import did not confirm success"
            print("Created the encrypted n8n digest credential through supported CLI; existing credentials preserved.")
        finally:
            docker("exec","-T","n8n","node","-e",
                   "const fs=require('fs');if(fs.existsSync(process.argv[1]))fs.unlinkSync(process.argv[1]);",private_path,check=False)
    finally:
        docker("exec","-T","n8n","node","-e",
               "const fs=require('fs');for(const p of process.argv.slice(1)){if(fs.existsSync(p))fs.unlinkSync(p);}",
               credential_export,"/tmp/flowforge-digest-owner.json",check=False)


if __name__=="__main__":main()
