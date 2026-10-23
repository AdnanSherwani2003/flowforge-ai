import {readJsonBody, RequestBodyError} from "@/lib/request-body";
import { NextResponse } from "next/server";
import { backendUrl, cookieOptions, SESSION_COOKIE, trustedOrigin } from "@/lib/security";
export async function POST(request: Request) {
 if (!trustedOrigin(request)) return NextResponse.json({detail:"Request origin rejected"}, {status:403});
 try {
  const body = await readJsonBody(request, 4096);
  if (typeof body.username !== "string" || typeof body.password !== "string" || body.username.length > 64 || body.password.length > 200)
   return NextResponse.json({detail:"Enter valid reviewer credentials"}, {status:400});
  const response = await fetch(backendUrl("/reviewer/login"), {method:"POST", headers:{"Content-Type":"application/json"},
   body:JSON.stringify({username:body.username,password:body.password}), cache:"no-store", signal:AbortSignal.timeout(8000)});
  if (!response.ok) return NextResponse.json({detail:response.status===429?"Too many attempts. Wait one minute.":"Sign-in failed. Check your credentials and try again."},{status:response.status===401?401:response.status===429?429:503});
  const data = await response.json();
  const result = NextResponse.json({ok:true});
  result.cookies.set(SESSION_COOKIE, data.token, {...cookieOptions(), maxAge:data.expires_in});
  return result;
 } catch (error) { if (error instanceof RequestBodyError) return NextResponse.json({detail:error.message},{status:error.status}); return NextResponse.json({detail:"The sign-in service is unavailable. Please try again."},{status:503}); }
}
