#!/usr/bin/env python3
"""Real published lead webhook acceptance; synthetic records intentionally remain."""
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from test_support_workflow import make_request, BACKEND_URL

ROOT=Path(__file__).resolve().parents[1]
WEBHOOK="http://localhost:5679/webhook/lead-intake"


def main(output=None):
    run="lead-"+uuid.uuid4().hex[:16]
    passed=0
    results=[]
    def check(ok,name):
        nonlocal passed
        assert ok,name
        passed+=1
    def get(path):return make_request(BACKEND_URL+path)
    def submit(payload,headers=None):
        return make_request(WEBHOOK,"POST",payload,headers=headers,timeout=12)
    def verify_trace(status,headers,body):
        h={k.lower():v for k,v in headers.items()}
        check(h.get("x-correlation-id")==body.get("correlation_id"),"Correlation response header")
        check(h.get("x-flowforge-execution-id")==body.get("execution_id"),"Execution response header")
        check(body.get("telemetry")=="best_effort","Explicit telemetry contract")
        for _ in range(60):
            code,_,row=get("/api/workflow-runs/"+body["execution_id"])
            if code==200:break
            time.sleep(.05)
        check(code==200 and row["workflow_name"]=="lead_intake","Lead telemetry saved")
        check(row["status_code"]==status and row["correlation_id"]==body["correlation_id"],"Telemetry status/trace")
        check(row.get("lead_id")==body.get("lead_id") and row.get("ticket_id") is None,"Correct entity linkage")
        check(set(row["safe_detail"]) <= {"status","duplicate","error_code","correlation_rejected","source_event_id_rejected","duplicate_reason"},"Telemetry allowlist")
        serialized=json.dumps(row)
        check("@example.com" not in serialized and "Synthetic Contact" not in serialized and "PRIVATE_CANARY" not in serialized,"No raw lead payload in telemetry")
        check("normalized_email" not in body and "name" not in body,"Webhook response minimizes PII")
        return row
    before=get("/api/mock-crm/leads?limit=1")[2]["total"]
    fixtures=json.loads((ROOT/"backend/tests/fixtures/lead_intake.json").read_text())["normal"]
    first=None
    for f in fixtures:
        payload=json.loads(json.dumps(f["payload"]).replace("{run}",run))
        headers=f.get("headers",{"X-Correlation-ID":"corr-"+run+"-"+f["name"]})
        status,h,body=submit(payload,headers)
        check(status==f["status"],f["name"]+" status: "+str(status))
        expected={201:"created",200:"duplicate_replayed",409:"conflict",422:"validation_error"}
        check(body.get("outcome")==expected[status],f["name"]+" routing")
        check("PRIVATE_CANARY" not in json.dumps(body),"Safe error response")
        row=verify_trace(status,h,body)
        if status in (200,201):
            first=first or body["lead_id"]
            check(body["lead_id"]==first,"Lead ID preserved")
            check(body.get("duplicate_reason")==f.get("reason"),"Duplicate reason")
            lead=get("/api/mock-crm/leads/"+first)[2]
            check(lead["name"]=="Synthetic Contact" and lead["normalized_email"]==run+"@example.com","No overwrite / normalized email")
            check(row["source_event_id"]==payload["source_event_id"].strip(),"Submitted event retained")
            if status==200:check(row["safe_detail"]["duplicate_reason"]==f["reason"],"Duplicate reason telemetry")
        results.append({"scenario":f["name"],"http_status":status,"outcome":body["outcome"],"execution_id":body["execution_id"],"lead_id":body.get("lead_id"),"duplicate_reason":body.get("duplicate_reason")})
        print("PASS:",f["name"],status,flush=True)
    for mode in ("same_event","same_email"):
        def worker(i):
            return submit({"source_event_id":run+"-"+mode+("-"+str(i) if mode=="same_email" else ""),
                "name":"Synthetic Concurrent","email":run+"-"+mode+"@example.com"},
                {"X-Correlation-ID":"corr-"+run+"-"+mode+"-"+str(i)})
        with ThreadPoolExecutor(max_workers=6) as pool:responses=list(pool.map(worker,range(6)))
        codes=[s for s,_,_ in responses]
        check(codes.count(201)==1 and codes.count(200)==5,mode+" one creator")
        check(len({b.get("lead_id") for _,_,b in responses})==1,mode+" one lead ID")
        for status,h,body in responses:verify_trace(status,h,body)
        results.append({"scenario":mode,"statuses":codes,"lead_id":responses[0][2]["lead_id"]})
        print("PASS:",mode,"one lead for six requests",flush=True)
    after=get("/api/mock-crm/leads?limit=1")[2]["total"]
    check(after==before+3,"Exactly three synthetic leads created across all normal cases")
    report={"passed":passed,"failed":0,"skipped":0,"scenario_count":len(results),"run":run,
            "lead_count_before":before,"lead_count_after":after,"results":results}
    (output or ROOT/"docs/evaluation/implementation-06-webhook.json").write_text(json.dumps(report,indent=2)+"\n")
    print(f"Lead webhook acceptance: {passed} passed, 0 failed, 0 skipped; {len(results)} scenarios")
    return report

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,help="Explicit acceptance report destination")
    main(parser.parse_args().output)
