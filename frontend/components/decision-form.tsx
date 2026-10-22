 "use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, X, ShieldCheck } from "lucide-react";
export default function DecisionForm({reviewId,enrichmentId,revision}:{reviewId:string;enrichmentId:string;revision:number}) {
 const router=useRouter();const [choice,setChoice]=useState<"approve"|"reject"|null>(null);
 const [note,setNote]=useState("");const [busy,setBusy]=useState(false);const guard=useRef(false);
 const [error,setError]=useState("");const [success,setSuccess]=useState("");
 const confirm=useRef<HTMLButtonElement>(null);const opener=useRef<HTMLButtonElement|null>(null);
 useEffect(()=>{if(choice)confirm.current?.focus();},[choice]);
 function close(){if(!guard.current){setChoice(null);opener.current?.focus();}}
 async function submit(){if(guard.current||!choice)return;guard.current=true;setBusy(true);setError("");
  try{const r=await fetch("/api/reviews/"+reviewId+"/"+choice,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({enrichment_id:enrichmentId,expected_revision:revision,note:choice==="reject"?note.trim():null})});
   const body=await r.json();if(!r.ok){if(r.status===401){router.push("/login?expired=1");return;}throw new Error(body.detail||"Decision could not be saved.");}
   setSuccess(body.status==="approved"?"Recommendation approved. The decision is recorded.":"Recommendation rejected. The decision is recorded.");setChoice(null);router.refresh();
  }catch(e){setError(e instanceof Error?e.message:"Decision could not be saved.");}finally{guard.current=false;setBusy(false);}}
 if(success)return <div role="status" className="success">{success}</div>;
 return <><p className="muted">Review the original request before deciding. Your decision is final for this recommendation.</p>
 <div style={{marginTop:20}}><label htmlFor="rejection-reason">Rejection reason <span className="muted">(required when rejecting)</span></label><textarea id="rejection-reason" maxLength={500} value={note} onChange={e=>setNote(e.target.value)} placeholder="Explain why this recommendation should not be accepted"/><small className="muted">{note.length}/500 characters</small></div>
 {error&&<div role="alert" className="error">{error}</div>}
 <div className="actions"><button className="btn primary" onClick={e=>{opener.current=e.currentTarget;setChoice("approve");}}><Check size={15}/>Approve recommendation</button><button className="btn" disabled={!note.trim()} onClick={e=>{opener.current=e.currentTarget;setChoice("reject");}}><X size={15}/>Reject recommendation</button></div>
 <p className="footer-note"><ShieldCheck size={13}/>Records your review only. No customer or business action follows.</p>
 {choice&&<div className="modal-backdrop" onKeyDown={e=>{if(e.key==="Escape")close();if(e.key==="Tab"){const list=e.currentTarget.querySelectorAll<HTMLButtonElement>("button");if(e.shiftKey&&document.activeElement===list[0]){e.preventDefault();list[list.length-1].focus();}else if(!e.shiftKey&&document.activeElement===list[list.length-1]){e.preventDefault();list[0].focus();}}}}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" aria-describedby="confirm-description"><h2 id="confirm-title">{choice==="approve"?"Approve this recommendation?":"Reject this recommendation?"}</h2><p id="confirm-description">This records a final decision for this exact AI recommendation. {choice==="reject"?"Your rejection reason will be saved with the decision.":"It does not change the original ticket or send a customer reply."}</p>{error&&<div role="alert" className="error">{error}</div>}<div className="actions"><button className="btn" disabled={busy} onClick={close}>Cancel</button><button ref={confirm} className={"btn "+(choice==="approve"?"primary":"danger")} disabled={busy} onClick={submit}>{busy?"Saving…":choice==="approve"?"Confirm approval":"Confirm rejection"}</button></div></section></div>}
 </>;
}
