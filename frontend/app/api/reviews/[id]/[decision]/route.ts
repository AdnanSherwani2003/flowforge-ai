import {readJsonBody, RequestBodyError} from "@/lib/request-body";
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { backendUrl, SESSION_COOKIE, trustedOrigin } from "@/lib/security";
export async function POST(request: Request, {params}:{params:Promise<{id:string;decision:string}>}) {
 if (!trustedOrigin(request)) return NextResponse.json({detail:"Request origin rejected"},{status:403});
 const {id,decision}=await params;
 if (!/^[a-f0-9-]{36}$/.test(id) || !["approve","reject"].includes(decision)) return NextResponse.json({detail:"Review operation not found"},{status:404});
 const token=(await cookies()).get(SESSION_COOKIE)?.value;
 if (!token) return NextResponse.json({detail:"Sign in to review recommendations"},{status:401});
 try {
  const body=await readJsonBody(request, 4096);
  const response=await fetch(backendUrl("/reviews/"+id+"/"+decision),{method:"POST", headers:{"Content-Type":"application/json",Authorization:"Bearer "+token},body:JSON.stringify(body),cache:"no-store",signal:AbortSignal.timeout(8000)});
  const messages:Record<number,string>={401:"Session expired. Sign in again.",404:"Review not found.",409:"This recommendation changed or already has a final decision. Refresh before continuing.",422:"Enter a valid reason of up to 500 printable characters."};
  if (!response.ok) return NextResponse.json({detail:messages[response.status]||"The decision could not be saved. Please retry."},{status:messages[response.status]?response.status:503});
  const data=await response.json(); return NextResponse.json({ok:true,duplicate:data.duplicate,status:data.status});
 } catch (error) { if (error instanceof RequestBodyError) return NextResponse.json({detail:error.message},{status:error.status}); return NextResponse.json({detail:"The decision service is unavailable. Refresh before retrying."},{status:503}); }
}
