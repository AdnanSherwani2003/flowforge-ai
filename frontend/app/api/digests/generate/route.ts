import {readJsonBody, RequestBodyError} from "@/lib/request-body";
import {cookies} from "next/headers";
import {NextResponse} from "next/server";
import {backendUrl,SESSION_COOKIE,trustedOrigin} from "@/lib/security";
export async function POST(request:Request){
 if(!trustedOrigin(request))return NextResponse.json({detail:"Request origin rejected"},{status:403});
 const token=(await cookies()).get(SESSION_COOKIE)?.value;
 if(!token)return NextResponse.json({detail:"Sign in to generate daily reports"},{status:401});
 try{
  const body=await readJsonBody(request,1024);
  const response=await fetch(backendUrl("/digests/generate"),{method:"POST",headers:{"Content-Type":"application/json",Authorization:"Bearer "+token},body:JSON.stringify(body),cache:"no-store",signal:AbortSignal.timeout(10000)});
  if(!response.ok)return NextResponse.json({detail:response.status===422?"Choose a valid completed reporting date.":response.status===401?"Session expired. Sign in again.":"The report service is unavailable. Retry with the same date."},{status:[401,422].includes(response.status)?response.status:503});
  const data=await response.json();return NextResponse.json({id:data.id,status:data.status,duplicate:data.duplicate},{status:response.status,headers:{"Cache-Control":"private, no-store"}});
 }catch(error){if(error instanceof RequestBodyError)return NextResponse.json({detail:error.message},{status:error.status});return NextResponse.json({detail:"The report service is unavailable. Retry with the same date."},{status:503});}
}
