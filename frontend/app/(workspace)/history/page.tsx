import { backend } from "@/lib/backend";
import type { ReviewList } from "@/lib/types";
import { ReviewTable, Pagination } from "@/components/ui";
import Refresh from "@/components/refresh";
export default async function History({searchParams}:{searchParams:Promise<{offset?:string}>}){
 const p=await searchParams;const offset=Math.min(10000,Math.max(0,Number(p.offset)||0));const data=await backend<ReviewList>("/reviews?final_only=true&limit=10&offset="+offset);
 return <><div className="page-heading"><div><span className="eyebrow">Decision record</span><h1 style={{marginTop:8}}>Review history</h1><p className="muted">Approved and rejected recommendations, with who decided and why.</p></div><Refresh/></div><section className="panel"><div className="panel-header"><h2>Recorded decisions</h2><span className="muted">{data.total} total</span></div><ReviewTable data={data} history/><Pagination total={data.total} offset={data.offset} limit={data.limit} path="/history?view=decisions"/></section></>;
}
