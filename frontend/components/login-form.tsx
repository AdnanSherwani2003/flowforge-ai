 "use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
export default function LoginForm(){const [busy,setBusy]=useState(false);const [error,setError]=useState("");const router=useRouter();
 return <form onSubmit={async e=>{e.preventDefault();if(busy)return;setBusy(true);setError("");const form=new FormData(e.currentTarget);
 try{const r=await fetch("/api/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:form.get("username"),password:form.get("password")})});const body=await r.json();if(!r.ok)throw new Error(body.detail);router.replace("/");router.refresh();}catch(e){setError(e instanceof Error?e.message:"Could not sign in.");setBusy(false);}}}>
 <div><label htmlFor="username">Reviewer name</label><input id="username" name="username" autoComplete="username" maxLength={64} required/></div>
 <div><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" maxLength={200} required/></div>
 {error&&<div role="alert" className="error">{error}</div>}<button className="btn primary" disabled={busy}>{busy?"Signing in…":"Sign in to workspace"}</button></form>;
}
