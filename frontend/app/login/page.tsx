import { Workflow, ShieldCheck } from "lucide-react";
import LoginForm from "@/components/login-form";
export default async function Login({searchParams}:{searchParams:Promise<{expired?:string}>}) {
 const {expired}=await searchParams;
 return <main className="login-wrap"><section className="login-intro"><div className="brand"><span className="brand-icon"><Workflow size={23}/></span>FlowForge AI</div><h1>AI suggests.<br/>You decide.</h1><p>A focused workspace for reviewing support recommendations, keeping human judgment at the heart of every decision.</p><p style={{fontSize:12}}>SUPPORT OPERATIONS · HUMAN REVIEW</p></section><section className="login-form-wrap"><div className="login-form"><span className="eyebrow">Reviewer workspace</span><h1 style={{marginTop:12}}>Welcome back</h1><p className="muted" style={{marginTop:10}}>Sign in to review recommendations and decision history.</p>{expired&&<div role="status" className="notice warning" style={{marginTop:20}}>Your session expired. Sign in again to continue.</div>}<LoginForm/><p className="footer-note"><ShieldCheck size={14}/>This workspace is restricted to the configured reviewer.</p></div></section></main>;
}
