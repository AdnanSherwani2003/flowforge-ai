import { Workflow, ShieldCheck, Circle } from "lucide-react";
import Navigation from "@/components/navigation";
import Logout from "@/components/logout";
import { backend } from "@/lib/backend";
export const dynamic="force-dynamic";
export default async function Workspace({children}:{children:React.ReactNode}){
 const session=await backend<{reviewer:string}>("/reviewer/session");
 return <><aside className="sidebar"><div className="brand"><span className="brand-icon"><Workflow size={23}/></span>FlowForge AI</div><small style={{margin:"8px 0 0 45px",color:"#8fb1a4",fontSize:10,letterSpacing:1.8}}>REVIEW WORKSPACE</small><Navigation/><div className="side-note"><ShieldCheck size={23}/><h3>Human judgment first</h3><p style={{marginTop:7}}>Every AI suggestion needs your review. Nothing is acted on automatically.</p></div></aside><div className="shell"><header className="topbar"><span className="muted" style={{fontSize:12}}>Support operations <span style={{padding:"0 10px"}}>/</span> Review workspace</span><div className="user"><span className="badge succeeded"><Circle size={6} fill="currentColor"/>Local workspace</span><span className="avatar" aria-hidden="true">{session.reviewer.slice(0,2).toUpperCase()}</span><span>{session.reviewer}</span><Logout/></div></header><main className="main">{children}</main></div></>;
}
