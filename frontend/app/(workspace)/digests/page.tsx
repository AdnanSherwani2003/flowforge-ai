import Link from "next/link";
import {backend} from "@/lib/backend";
import type {DigestList} from "@/lib/digests";
import DigestControls from "@/components/digest-controls";
import DigestReport from "@/components/digest-report";
import {Empty,Pagination} from "@/components/ui";
export default async function Digests({searchParams}:{searchParams:Promise<{date?:string;offset?:string}>}){
 const p=await searchParams;const offset=Math.min(10000,Math.max(0,Number(p.offset)||0));
 const listing=await backend<DigestList>("/digests?limit=10&offset="+offset);
 const valid=!!p.date&&/^\d{4}-\d{2}-\d{2}$/.test(p.date)&&p.date>="2000-01-01"&&p.date<=listing.previous_completed_date&&!isNaN(Date.parse(p.date))&&new Date(p.date).toISOString().slice(0,10)===p.date;
 const selected=valid?p.date!:listing.previous_completed_date;
 const current=listing.items.find(r=>r.reporting_date===selected);
 const report=current||(await backend<DigestList>("/digests?reporting_date="+encodeURIComponent(selected)+"&limit=1")).items[0]||null;
 return <><div className="page-heading"><div><span className="eyebrow">Daily operations</span><h1 style={{marginTop:8}}>Daily digest</h1><p className="muted">Daily activity and the backlog captured when the report was generated.</p></div></div>
 <section className="panel"><DigestControls key={selected} reportingDate={selected} maxDate={listing.previous_completed_date}/></section>
 {p.date&&!valid&&<div className="error" role="alert">Choose a valid completed reporting date. Showing the previous completed day.</div>}
 <DigestReport report={report}/>
 <section className="panel"><div className="panel-header"><div><h2>Saved reports</h2><p>{listing.reporting_timezone} · One frozen report per day</p></div><span className="muted">{listing.total} total</span></div>
 {!listing.items.length?<Empty title="No saved reports yet" text="Choose a completed date and generate your first daily digest."/>:<div className="table-scroll"><table><thead><tr><th scope="col">Reporting date</th><th scope="col">Status</th><th scope="col">Generated</th><th scope="col">Report</th></tr></thead><tbody>{listing.items.map(d=><tr key={d.id}><td>{d.reporting_date}</td><td><span className="badge succeeded">Ready</span></td><td>{new Intl.DateTimeFormat("en-GB",{dateStyle:"medium",timeStyle:"short",timeZone:d.reporting_timezone}).format(new Date(d.generated_at))}</td><td><Link className="btn small" href={"/digests?date="+d.reporting_date}>View {d.reporting_date}</Link></td></tr>)}</tbody></table></div>}
 <Pagination total={listing.total} offset={listing.offset} limit={listing.limit} path={"/digests?date="+selected}/></section></>;
}
