#!/usr/bin/env python3
"""Authenticated API + Next.js integration; aggregate-only saved evidence."""
import json
import argparse
import uuid
from datetime import date,timedelta,datetime
from pathlib import Path
from test_review_integration import request,credentials,BACKEND,FRONTEND
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"docs/evaluation/implementation-07-integration.json")
    args=parser.parse_args()
    checks=0
    def check(ok,label):
        nonlocal checks
        assert ok,label
        checks+=1
    creds=credentials()
    check(request(BACKEND+"/digests")[0]==401,"Digest list protected")
    check(request(BACKEND+"/digests/generate",{})[0]==401,"Generation protected")
    check("Welcome back" in request(FRONTEND+"/digests")[1],"Protected dashboard")
    check(request(FRONTEND+"/api/digests/generate",{},{"Origin":FRONTEND})[0]==401,"Next proxy protected")
    status,auth=request(BACKEND+"/reviewer/login",creds)
    check(status==200,"Reviewer login")
    headers={"Authorization":"Bearer "+auth["token"]}
    check(request(FRONTEND+"/api/auth/login",creds,{"Origin":FRONTEND},True)[0]==200,"HttpOnly dashboard login")
    check(request(FRONTEND+"/api/digests/generate",{},{"Origin":"http://localhost:4444"},True)[0]==403,"Cross-origin generation rejected")
    settings={}
    for line in (ROOT/".env").read_text().splitlines():
        if "=" in line:
            k,v=line.split("=",1);settings[k]=v.strip().strip("'\"")
    service_header={"X-FlowForge-Digest-Key":settings["FLOWFORGE_DIGEST_SERVICE_KEY"]}
    check(request(BACKEND+"/digests",headers=service_header)[0]==401,"Service key cannot view reports")
    check(request(BACKEND+"/reviews",headers=service_header)[0]==401,"Service key cannot review")
    check(request(BACKEND+"/digests/generate",{},{"X-FlowForge-Digest-Key":"invalid"})[0]==401,"Wrong service key rejected")
    day=date(2000,1,1)+timedelta(days=int(uuid.uuid4().hex[:6],16)%300)
    for _ in range(30):
        if request(BACKEND+"/digests?reporting_date="+day.isoformat(),headers=headers)[1]["total"]==0:break
        day+=timedelta(days=1)
    body={"reporting_date":day.isoformat()}
    status,created=request(BACKEND+"/digests/generate",body,headers)
    check(status==201 and not created["duplicate"],"Manual backfill creates report")
    check(created["status"]=="ready" and created["reporting_timezone"]=="Asia/Kolkata","Correct report status/timezone")
    check(created["period_start"].startswith((day-timedelta(days=1)).isoformat()+"T18:30:00"),"UTC start boundary")
    check(created["period_end"].startswith(day.isoformat()+"T18:30:00"),"UTC end boundary")
    activity=created["metrics"]["activity"]
    values=[value for group in activity.values() for value in (group.values() if isinstance(group,dict) else [group])]
    check(all(v==0 for v in values),"Historical empty activity")
    check(created["metrics"]["snapshot"]["pending_reviews"]>=0,"Separate current snapshot")
    status,replayed=request(BACKEND+"/digests/generate",body,service_header)
    check(status==200 and replayed["duplicate"],"Scheduled credential replays")
    check(all(created[k]==replayed[k] for k in ("id","metrics","generated_at","period_start","period_end")),"Frozen report unchanged")
    check(request(BACKEND+"/digests/"+created["id"],headers=headers)[1]["metrics"]==created["metrics"],"Protected detail")
    check(request(BACKEND+"/digests?reporting_date="+day.isoformat(),headers=headers)[1]["total"]==1,"Unique report identity")
    check(request(BACKEND+"/digests/generate",{"reporting_date":"not-a-date"},headers)[0]==422,"Malformed date rejected")
    check(request(BACKEND+"/digests/generate",{"reporting_date":"2999-01-01"},headers)[0]==422,"Future date rejected")
    check(request(BACKEND+"/digests/generate",{**body,"refresh":True},headers)[0]==422,"Implicit refresh rejected")
    check(request(FRONTEND+"/api/digests/generate",body,{"Origin":FRONTEND},True)[1]["duplicate"],"Next generation proxy replay")
    status,html=request(FRONTEND+"/digests?date="+day.isoformat(),cookies=True)
    check(status==200 and "Daily digest" in html and "Backlog at generation" in html,"Actual dashboard renders report")
    check("No activity recorded during this day" in html,"Empty activity visible")
    check(settings["FLOWFORGE_DIGEST_SERVICE_KEY"] not in html and auth["token"] not in html,"No credentials in HTML")
    check(request(BACKEND+"/digests?limit=51",headers=headers)[0]==422,"Bounded pagination")
    result={"passed":checks,"failed":0,"skipped":0,"backfill_report_id":created["id"],"backfill_date":day.isoformat(),"report":created}
    args.output.write_text(json.dumps(result,indent=2)+"\n")
    print(f"Digest integration: {checks} passed, 0 failed, 0 skipped")
    return result

if __name__=="__main__":main()
