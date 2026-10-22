import { backend } from "@/lib/backend";
import type { ReviewList } from "@/lib/types";
import { ReviewTable, Pagination } from "@/components/ui";
import Refresh from "@/components/refresh";
export default async function Queue({searchParams}:{searchParams:Promise<{status?:string;offset?:string}>}){
 const p=await searchParams;const status=["pending","attention","approved","rejected"].includes(p.status||"")?p.status!:"pending";const offset=Math.min(10000,Math.max(0,Number(p.offset)||0));
 const data=await backend<ReviewList>("/reviews?status="+status+"&limit=10&offset="+offset);
 return <><div className="page-heading"><div><span className="eyebrow">Human review</span><h1 style={{marginTop:8}}>Review queue</h1><p className="muted">Inspect the original request, assess the recommendation, and record your decision.</p></div><Refresh/></div><section className="panel"><form className="filters" action="/reviews"><label htmlFor="status-filter" style={{margin:0}}>Show</label><select id="status-filter" name="status" defaultValue={status}><option value="pending">Awaiting review</option><option value="attention">Needs attention</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select><button className="btn small">Apply filter</button></form><ReviewTable data={data}/><Pagination total={data.total} offset={data.offset} limit={data.limit} path={"/reviews?status="+status}/></section></>;
}
