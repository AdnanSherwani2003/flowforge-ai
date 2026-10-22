 "use client";
import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { RefreshCw } from "lucide-react";
export default function Refresh() { const router=useRouter();const [pending,start]=useTransition();return <button className="btn" disabled={pending} onClick={()=>start(()=>router.refresh())}><RefreshCw size={14}/>{pending?"Refreshing…":"Refresh"}</button>; }
