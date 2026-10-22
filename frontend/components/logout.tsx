 "use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
export default function Logout(){const router=useRouter();const [busy,setBusy]=useState(false);const [error,setError]=useState(false);
 return <div><button className="btn small" disabled={busy} onClick={async()=>{setBusy(true);try{const r=await fetch("/api/auth/logout",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"});if(!r.ok)throw Error();router.push("/login");router.refresh();}catch{setError(true);setBusy(false);}}}>{busy?"Signing out…":"Sign out"}</button>{error&&<span role="alert"> Could not sign out. Retry.</span>}</div>;}
