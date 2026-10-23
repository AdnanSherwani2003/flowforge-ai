import {render,screen,fireEvent,waitFor} from "@testing-library/react";
import {test,expect,vi,beforeEach} from "vitest";
import DigestReport from "@/components/digest-report";
import DigestControls from "@/components/digest-controls";
import DigestError from "@/app/(workspace)/digests/error";
import type {Digest} from "@/lib/digests";
const {push,refresh}=vi.hoisted(()=>({push:vi.fn(),refresh:vi.fn()}));
vi.mock("next/navigation",()=>({useRouter:()=>({push,refresh})}));
const report:Digest={id:"digest-1",reporting_date:"2025-12-31",reporting_timezone:"Asia/Kolkata",
 period_start:"2025-12-30T18:30:00Z",period_end:"2025-12-31T18:30:00Z",generated_at:"2026-01-01T03:30:00Z",
 metrics_version:1,status:"ready",duplicate:false,
 metrics:{activity:{tickets_created:12,canonical_leads_created:3,
 lead_requests_observed:{created_records:4,event_replays:8,email_matches:6,legacy_duplicates:0},
 enrichment_results_completed:{succeeded:5,needs_review:2,unavailable:1},review_decisions:{approved:4,rejected:2}},
 snapshot:{pending_reviews:19,attention_reviews:7,processing_enrichments:1}}};
beforeEach(()=>{vi.clearAllMocks();vi.stubGlobal("fetch",vi.fn());});
test("actual activity and backlog have separate sections",()=>{
 render(<DigestReport report={report}/>);
 expect(screen.getByRole("heading",{name:"Activity during reporting day"})).toBeInTheDocument();
 expect(screen.getByRole("heading",{name:"Backlog at generation"})).toBeInTheDocument();
 for(const n of ["12","3","19","7"])expect(screen.getAllByText(n).length).toBeGreaterThan(0);
 expect(screen.getByText("Event replays")).toBeInTheDocument();
 expect(screen.getByText("Existing-email matches")).toBeInTheDocument();
 expect(screen.getByText(/snapshot is frozen/)).toBeInTheDocument();
});
test("missing report has an explicit empty state",()=>{
 render(<DigestReport report={null}/>);
 expect(screen.getByText("No report for this date")).toBeInTheDocument();
 expect(screen.queryByText("Support tickets created")).toBeNull();
});
test("empty activity does not erase the current backlog",()=>{
 const empty={...report,metrics:{...report.metrics,activity:{tickets_created:0,canonical_leads_created:0,
 lead_requests_observed:{created_records:0,event_replays:0,email_matches:0,legacy_duplicates:0},
 enrichment_results_completed:{succeeded:0,needs_review:0,unavailable:0},review_decisions:{approved:0,rejected:0}}}};
 render(<DigestReport report={empty}/>);
 expect(screen.getByText(/No activity recorded/)).toBeInTheDocument();
 expect(screen.getByText("19")).toBeInTheDocument();
});
test("generation uses only selected date and refreshes report",async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({duplicate:false}),{status:201}));
 render(<DigestControls reportingDate="2025-12-31" maxDate="2026-01-01"/>);
 fireEvent.click(screen.getByRole("button",{name:"Generate report"}));
 expect(await screen.findByRole("status")).toHaveTextContent("Report saved");
 expect(fetch).toHaveBeenCalledWith("/api/digests/generate",expect.objectContaining({body:JSON.stringify({reporting_date:"2025-12-31"})}));
 expect(push).toHaveBeenCalledWith("/digests?date=2025-12-31");expect(refresh).toHaveBeenCalledOnce();
});
test("same-day replay reports the frozen existing result",async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({duplicate:true})));
 render(<DigestControls reportingDate="2025-12-31" maxDate="2026-01-01"/>);
 fireEvent.click(screen.getByRole("button",{name:"Generate report"}));
 expect(await screen.findByRole("status")).toHaveTextContent("original snapshot is preserved");
});
test("concurrent clicks cannot send two generation requests",async()=>{
 let finish!:(r:Response)=>void;vi.mocked(fetch).mockReturnValue(new Promise(r=>{finish=r;}));
 render(<DigestControls reportingDate="2025-12-31" maxDate="2026-01-01"/>);
 const button=screen.getByRole("button",{name:"Generate report"});fireEvent.click(button);fireEvent.click(button);
 expect(fetch).toHaveBeenCalledOnce();finish(new Response(JSON.stringify({duplicate:false})));await screen.findByRole("status");
});
test("unavailable service does not fabricate success",async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response("{}",{status:503}));
 render(<DigestControls reportingDate="2025-12-31" maxDate="2026-01-01"/>);
 fireEvent.click(screen.getByRole("button",{name:"Generate report"}));
 expect(await screen.findByRole("alert")).toHaveTextContent("unavailable");
 expect(screen.queryByRole("status")).toBeNull();
});
test("invalid reporting date feedback is explicit",async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response("{}",{status:422}));
 render(<DigestControls reportingDate="2025-12-31" maxDate="2026-01-01"/>);
 fireEvent.click(screen.getByRole("button",{name:"Generate report"}));
 expect(await screen.findByRole("alert")).toHaveTextContent("completed reporting date");
});
test("expired session goes back to secure login",async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response("{}",{status:401}));
 render(<DigestControls reportingDate="2025-12-31" maxDate="2026-01-01"/>);
 fireEvent.click(screen.getByRole("button",{name:"Generate report"}));
 await waitFor(()=>expect(push).toHaveBeenCalledWith("/login?expired=1"));
});
test("manual date selection can view a previous date",()=>{
 render(<DigestControls reportingDate="2025-12-31" maxDate="2026-01-01"/>);
 fireEvent.change(screen.getByLabelText("Reporting date"),{target:{value:"2020-01-01"}});
 fireEvent.submit(screen.getByRole("button",{name:"View report"}).closest("form")!);
 expect(push).toHaveBeenCalledWith("/digests?date=2020-01-01");expect(fetch).not.toHaveBeenCalled();
});
test("future dates cannot be generated by dashboard controls",()=>{
 render(<DigestControls reportingDate="2026-01-02" maxDate="2026-01-01"/>);
 expect(screen.getByRole("button",{name:"Generate report"})).toBeDisabled();
});
test("digest-specific unavailable page offers recovery",()=>{
 const reset=vi.fn();render(<DigestError reset={reset}/>);
 expect(screen.getByText("Daily reports are unavailable")).toBeInTheDocument();
 fireEvent.click(screen.getByRole("button",{name:"Try again"}));expect(reset).toHaveBeenCalledOnce();
});

test("native date value is authoritative even before a React change event",async()=>{
 vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({duplicate:false}),{status:201}));
 render(<DigestControls reportingDate="2025-12-31" maxDate="2026-01-01"/>);
 (screen.getByLabelText("Reporting date") as HTMLInputElement).value="2020-01-02";
 fireEvent.click(screen.getByRole("button",{name:"Generate report"}));
 await screen.findByRole("status");
 expect(fetch).toHaveBeenCalledWith("/api/digests/generate",expect.objectContaining({body:JSON.stringify({reporting_date:"2020-01-02"})}));
});
