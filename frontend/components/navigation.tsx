 "use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, ListChecks, History, CalendarDays } from "lucide-react";
export default function Navigation() {
 const path=usePathname();
 const items=[{href:"/",label:"Overview",icon:LayoutDashboard},{href:"/reviews",label:"Review queue",icon:ListChecks},{href:"/history",label:"Decision history",icon:History},{href:"/digests",label:"Daily digest",icon:CalendarDays}];
 return <nav aria-label="Main navigation">{items.map(({href,label,icon:Icon})=><Link key={href} href={href} className={"nav-link "+((href==="/" ? path==="/" : path.startsWith(href))?"active":"")} aria-current={(href==="/" ? path==="/" : path.startsWith(href))?"page":undefined}><Icon size={17}/>{label}</Link>)}</nav>;
}
