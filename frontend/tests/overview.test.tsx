import {render,screen} from "@testing-library/react";
import {test,expect,vi} from "vitest";
import Overview from "@/app/(workspace)/page";
vi.mock("@/lib/backend",()=>({backend:vi.fn(async(path:string)=>path==="/reviews/summary"?{
 total_tickets:123,pending:4,approved:7,rejected:2,attention:3,enrichment:{succeeded:8,needs_review:2,unavailable:1}
}:{items:[],total:0,limit:5,offset:0})}));
vi.mock("@/components/refresh",()=>({default:()=> <button>Refresh</button>}));
test("overview renders server API statistics rather than fixed demo numbers",async()=>{
 render(await Overview());for(const value of ["123","4","7","2"])expect(screen.getAllByText(value).length).toBeGreaterThan(0);
 expect(screen.getByRole("heading",{name:"Operations overview"})).toBeInTheDocument();
 expect(screen.getByText("Nothing awaiting review")).toBeInTheDocument();
});
