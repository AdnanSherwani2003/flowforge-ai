#!/usr/bin/env python3
"""Six-node disposable webhook adapter tests the five production digest nodes.

No production workflow is changed. Temporary credential material is mode 0600
and removed with the test directory; n8n stores it encrypted in disposable tmpfs.
"""
import copy,json,os,tempfile,time,uuid
from datetime import date,timedelta
from pathlib import Path
from test_workflow_faults import docker,ROOT
from test_support_workflow import make_request,BACKEND_URL
from test_review_integration import request,credentials,BACKEND


def main():
    tag="ff-digest-fault-"+uuid.uuid4().hex[:8]
    proxy,engine=tag+"-proxy",tag+"-n8n"
    started=[];checks=0;results=[]
    def check(ok,label):
        nonlocal checks
        assert ok,label
        checks+=1;print("PASS:",label,flush=True)
    def port(name,p):
        return json.loads(docker("inspect",name).stdout)[0]["NetworkSettings"]["Ports"][str(p)+"/tcp"][0]["HostPort"]
    values={k:v.strip().strip("'\"") for line in (ROOT/".env").read_text().splitlines() if "=" in line for k,v in [line.split("=",1)]}
    token=request(BACKEND+"/reviewer/login",credentials())[1]["token"]
    auth={"Authorization":"Bearer "+token}
    def reports(day):return request(BACKEND+"/digests?reporting_date="+day,headers=auth)[1]
    with tempfile.TemporaryDirectory(prefix=tag) as scratch:
        folder=Path(scratch);folder.chmod(0o755)
        workflow=copy.deepcopy(json.loads((ROOT/"workflows/daily_operations_digest.json").read_text()))
        workflow.update(id="IsolatedDigestCheck",name="Isolated digest fault verification")
        scheduled=copy.deepcopy(workflow)
        scheduled.update(id="IsolatedDigestSchedule",name="Isolated accelerated digest schedule")
        scheduled["nodes"][0]["parameters"]["rule"]["interval"][0]["expression"]="*/10 * * * * *"
        scheduled["nodes"][1]["parameters"]["jsonOutput"]=scheduled["nodes"][1]["parameters"]["jsonOutput"].replace(
            "execution_id: String($execution.id)", "execution_id: '"+tag+"-scheduled-' + $execution.id").replace(
            "'corr-digest-' + $execution.id", "'corr-"+tag+"-scheduled-' + $execution.id")
        scheduled["nodes"][-1]["parameters"]["jsonBody"]=scheduled["nodes"][-1]["parameters"]["jsonBody"].replace(
            "workflow_name: 'daily_operations_digest'", "workflow_name: '"+tag+"-scheduled'")
        schedule=workflow["nodes"][0]
        schedule.update(type="n8n-nodes-base.webhook",typeVersion=2,webhookId="digest-check",
                        parameters={"httpMethod":"POST","path":"digest-check","responseMode":"responseNode","options":{}})
        prep=workflow["nodes"][1]
        prep["parameters"]["jsonOutput"]="={{ JSON.stringify({reporting_date: $json.body.reporting_date, fault: $json.body.fault, execution_id: '"+tag+"-' + $execution.id, correlation_id: 'corr-"+tag+"-' + $execution.id}) }}"
        call=workflow["nodes"][2]
        call["parameters"]["url"]="={{ $json.fault === 'refused' ? 'http://"+proxy+":8081/' : 'http://"+proxy+":8080/' + $json.fault }}"
        telemetry=workflow["nodes"][-1]
        telemetry["parameters"]["jsonBody"]=telemetry["parameters"]["jsonBody"].replace("workflow_name: 'daily_operations_digest'","workflow_name: '"+tag+"'")
        telemetry["parameters"]["url"]="={{ $('Prepare Reporting Date').item.json.fault === 'telemetry-down' ? 'http://"+proxy+":8080/telemetry-unavailable' : 'http://backend:8001/api/workflow-runs' }}"
        response={"id":"digest-test-response","name":"Respond to Isolated Test","type":"n8n-nodes-base.respondToWebhook","typeVersion":1.1,"position":[900,400],
                  "parameters":{"options":{"responseCode":"={{ $json.status_code }}"}}}
        workflow["nodes"].insert(-1,response)
        workflow["connections"]["Normalize Digest Outcome"]={"main":[[{"node":response["name"],"type":"main","index":0}]]}
        workflow["connections"][response["name"]]={"main":[[{"node":telemetry["name"],"type":"main","index":0}]]}
        (folder/"workflow.json").write_text(json.dumps([workflow,scheduled]))
        (folder/"server.py").write_text((ROOT/"scripts/fault_proxy.py").read_text())
        secret=folder/"credential.json"
        secret.write_text(json.dumps([{"id":"FlowForgeDigestApi01","name":"FlowForge Digest Service","type":"httpHeaderAuth",
            "data":{"name":"X-FlowForge-Digest-Key","value":values["FLOWFORGE_DIGEST_SERVICE_KEY"]}}]))
        secret.chmod(0o600)
        try:
            docker("run","--rm","-d","--name",proxy,"--network","flowforge-ai_default","-p","127.0.0.1::8080",
                   "--mount",f"type=bind,src={folder},dst=/harness,readonly","-e","FAULT_BACKEND_PATH=/api/digests/generate",
                   "-e","FAULT_DELAY_SECONDS=10","flowforge-ai-backend","python","/harness/server.py")
            started.append(proxy)
            docker("run","--rm","-d","--name",engine,"--network","flowforge-ai_default","-p","127.0.0.1::5678",
                "--tmpfs","/home/node/.n8n:uid=1000,gid=1000,mode=700","--mount",f"type=bind,src={folder},dst=/harness,readonly",
                "-e","N8N_DIAGNOSTICS_ENABLED=false","-e","N8N_SECURE_COOKIE=false","-e","EXECUTIONS_DATA_SAVE_ON_SUCCESS=none",
                "-e","EXECUTIONS_DATA_SAVE_ON_ERROR=none","-e","EXECUTIONS_DATA_PRUNE=false","-e","N8N_USE_WORKFLOW_PUBLICATION_SERVICE=false",
                "--entrypoint","/bin/sh","n8nio/n8n:2.43.8","-c",
                "n8n import:workflow --input=/harness/workflow.json && n8n import:credentials --input=/harness/credential.json && n8n publish:workflow --id=IsolatedDigestCheck && n8n publish:workflow --id=IsolatedDigestSchedule && n8n start")
            started.append(engine)
            url="http://127.0.0.1:"+port(engine,5678)
            for _ in range(450):
                if make_request(url+"/healthz/readiness",timeout=1)[0]==200:break
                assert json.loads(docker("inspect",engine).stdout)[0]["State"]["Running"],"Disposable n8n stopped"
                time.sleep(.2)
            check(make_request(url+"/healthz/readiness")[0]==200,"Disposable n8n ready")
            webhook=url+"/webhook/digest-check"
            for _ in range(150):
                code,_,body=make_request(webhook,"POST",{"reporting_date":"2002-01-01","fault":"503"})
                if code==503 and body.get("outcome")=="service_unavailable":break
                time.sleep(.2)
            check(code==503 and body.get("outcome")=="service_unavailable","Isolated adapter registered")
            for _ in range(30):
                base=date(2002,1,1)+timedelta(days=int(uuid.uuid4().hex[:6],16)%6000)
                if all(reports((base+timedelta(days=i)).isoformat())["total"]==0 for i in range(7)):
                    break
            else:
                raise AssertionError("No fresh bounded synthetic reporting window found")
            for i,mode in enumerate(("503","refused","timeout","after-persist","unauthorized","validation","telemetry-down")):
                day=(base+timedelta(days=i)).isoformat()
                assert reports(day)["total"]==0,"Choose a fresh synthetic reporting day"
                payload={"reporting_date":"invalid-date" if mode=="validation" else day,"fault":mode}
                began=time.monotonic();status,_,body=make_request(webhook,"POST",payload,timeout=14);elapsed=time.monotonic()-began
                expected=401 if mode=="unauthorized" else 422 if mode=="validation" else 201 if mode=="telemetry-down" else 503
                check(status==expected,mode+" HTTP outcome")
                check(body.get("outcome")=={401:"authentication_required",422:"validation_error",201:"created",503:"service_unavailable"}[expected],mode+" routing")
                check(values["FLOWFORGE_DIGEST_SERVICE_KEY"] not in json.dumps(body) and "SYNTHETIC_PRIVATE_ERROR_CANARY" not in json.dumps(body),mode+" sanitized")
                if mode in ("timeout","after-persist"):check(7.5<=elapsed<=11,mode+" bounded at eight seconds")
                count=reports(day)["total"]
                check(count==(1 if mode in ("after-persist","telemetry-down") else 0),mode+" persistence boundary")
                if mode in ("503","after-persist"):
                    old=reports(day)["items"]
                    status,_,retry=make_request(webhook,"POST",{**payload,"fault":"success"})
                    check(status==(200 if old else 201),mode+" safe retry")
                    status,_,repeat=make_request(webhook,"POST",{**payload,"fault":"success"})
                    check(status==200 and repeat["digest_id"]==retry["digest_id"],mode+" same report replay")
                    check(reports(day)["total"]==1,mode+" exactly one report")
                if mode=="telemetry-down":
                    for _ in range(50):
                        stats=make_request("http://127.0.0.1:"+port(proxy,8080))[2]
                        if stats.get("telemetry-unavailable"):break
                        time.sleep(.1)
                    check(stats.get("telemetry-unavailable")==1,"Telemetry outage reached proxy")
                    check(make_request(BACKEND_URL+"/api/workflow-runs/"+body["execution_id"])[0]==404,"Best effort telemetry failure preserves response")
                results.append({"mode":mode,"status":status if mode not in ("503","after-persist") else 503,"initial_elapsed_ms":round(elapsed*1000)})
            for _ in range(150):
                runs=make_request(BACKEND_URL+"/api/workflow-runs?limit=100")[2]["items"]
                scheduled_runs=[x for x in runs if x["workflow_name"]==tag+"-scheduled"]
                if scheduled_runs:break
                time.sleep(.1)
            check(bool(scheduled_runs),"Actual isolated schedule timer fired")
            today=request(BACKEND+"/digests",headers=auth)[1]["previous_completed_date"]
            expected_report=reports(today)["items"][0]
            check(all(x["digest_id"]==expected_report["id"] for x in scheduled_runs),"Timer selected previous completed local day")
            check(all(x["outcome"]=="duplicate_replayed" and x["status_code"]==200 for x in scheduled_runs),"Timer safely replayed existing immutable report")
            check(values["FLOWFORGE_DIGEST_SERVICE_KEY"] not in json.dumps(scheduled_runs) and all(set(x["safe_detail"])=={"status","duplicate","error_code"} for x in scheduled_runs),"Scheduled telemetry contains safe metadata only")
        except Exception:
            if engine in started:
                # Synthetic engine diagnostics only; no credential values printed.
                log=docker("logs","--tail","18",engine,check=False)
                safe=(log.stdout+log.stderr).replace(values["FLOWFORGE_DIGEST_SERVICE_KEY"],"[redacted]")
                print(safe)
            raise
        finally:
            for name in reversed(started):docker("stop","--time","10",name,check=False)
    evidence={"passed":checks,"failed":0,"skipped":0,"scenarios":results}
    (ROOT/"docs/evaluation/implementation-07-faults.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(f"Digest faults: {checks} passed, 0 failed, 0 skipped")

if __name__=="__main__":main()
