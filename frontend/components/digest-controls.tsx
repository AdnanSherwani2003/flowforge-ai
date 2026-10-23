"use client";
import {useRef,useState} from "react";
import {useRouter} from "next/navigation";
export default function DigestControls({reportingDate,maxDate}:{reportingDate:string;maxDate:string}){
 const router=useRouter();const inflight=useRef(false);const form=useRef<HTMLFormElement>(null);
 const chosenDay=()=>String(new FormData(form.current!).get("reporting_date")||"");
 const [day,setDay]=useState(reportingDate);const [busy,setBusy]=useState(false);
 const [message,setMessage]=useState("");const [error,setError]=useState("");
 async function generate(){
  if(inflight.current)return;
  const selectedDay=chosenDay();
  inflight.current=true;setBusy(true);setError("");setMessage("");
  try{
   const response=await fetch("/api/digests/generate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reporting_date:selectedDay})});
   if(response.status===401){router.push("/login?expired=1");return;}
   if(!response.ok){setError(response.status===422?"Choose a valid completed reporting date.":"The report service is unavailable. Retry with the same date.");return;}
   const data=await response.json();
   setMessage(data.duplicate?"Existing report opened; its original snapshot is preserved.":"Report saved with a snapshot of the current backlog.");
   router.push("/digests?date="+encodeURIComponent(selectedDay));router.refresh();
  }catch{setError("The report service is unavailable. Retry with the same date.");}
  finally{inflight.current=false;setBusy(false);}
 }
 return <><form ref={form} className="filters" onSubmit={e=>{e.preventDefault();setError("");setMessage("");router.push("/digests?date="+encodeURIComponent(chosenDay()));}}>
  <div><label htmlFor="digest-date">Reporting date</label><input id="digest-date" name="reporting_date" type="date" min="2000-01-01" max={maxDate} required value={day} onChange={e=>setDay(e.target.value)} onInput={e=>setDay(e.currentTarget.value)}/></div>
  <button className="btn" type="submit" disabled={busy}>View report</button>
  <button className="btn primary" type="button" onClick={generate} disabled={busy||!day||day>maxDate||day<"2000-01-01"}>{busy?"Generating…":"Generate report"}</button>
 </form>{message&&<div className="success" role="status">{message}</div>}{error&&<div className="error" role="alert">{error}</div>}</>;
}
