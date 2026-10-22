import Link from "next/link";
import { Inbox, ArrowUpRight } from "lucide-react";
import type { ReviewList } from "@/lib/types";
export const human = (s:string)=>s.replaceAll("_"," ");
export function date(s:string|null){return s?new Intl.DateTimeFormat("en-GB",{day:"2-digit",month:"short",year:"numeric",timeZone:"Asia/Kolkata"}).format(new Date(s)):"—";}
export function dateTime(s:string|null){return s?new Intl.DateTimeFormat("en-GB",{dateStyle:"medium",timeStyle:"short",timeZone:"Asia/Kolkata"}).format(new Date(s)):"—";}
export function Badge({value}:{value:string}) {return <span className={"badge "+value}>{human(value==="attention"?"needs_review":value)}</span>;}
export function Empty({title="Nothing awaiting review",text="New recommendations will appear here after ticket analysis completes."}:{title?:string;text?:string}) {return <div className="empty"><Inbox size={30}/><h3>{title}</h3><p>{text}</p></div>;}
export function ReviewTable({data,history=false}:{data:ReviewList;history?:boolean}) {
 if(!data.items.length)return <Empty title={history?"No decisions yet":undefined} text={history?"Approved and rejected recommendations will appear here.":undefined}/>;
 return <div className="table-scroll"><table><thead><tr><th scope="col">Ticket</th>{!history&&<><th scope="col">AI category</th><th scope="col">Priority</th></>}<th scope="col">{history?"Decision":"Status"}</th><th scope="col">{history?"Reviewer / date":"Created"}</th>{history&&<th scope="col">Review note</th>}<th scope="col"><span className="sr-only">Open review</span></th></tr></thead><tbody>{data.items.map(r=><tr key={r.id}><td><div className="subject">{r.subject}</div><div className="reference">{r.ticket_id.slice(0,8)}</div></td>{!history&&<><td>{r.enrichment_status==="succeeded"?human(r.category):"No valid suggestion"}</td><td><Badge value={r.priority}/></td></>}<td><Badge value={r.status}/>{r.superseded&&<small className="muted"> · Earlier version</small>}</td><td>{history&&<div>{r.reviewer}</div>}<span className="muted">{history?dateTime(r.decided_at):date(r.created_at)}</span></td>{history&&<td className="history-note">{r.note||"—"}</td>}<td><Link className="btn small" href={"/reviews/"+r.id}>View <ArrowUpRight size={13}/></Link></td></tr>)}</tbody></table></div>;
}
export function Pagination({total,offset,limit,path}:{total:number;offset:number;limit:number;path:string}) {
 return <div className="pagination"><span>{total?offset+1:0}–{Math.min(offset+limit,total)} of {total} items</span><div className="actions" style={{marginTop:0}}>{offset>0&&<Link className="btn small" href={path+"&offset="+Math.max(0,offset-limit)}>Previous</Link>}{offset+limit<total&&<Link className="btn small" href={path+"&offset="+(offset+limit)}>Next</Link>}</div></div>;
}
