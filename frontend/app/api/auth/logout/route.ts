import { NextResponse } from "next/server";
import { SESSION_COOKIE, trustedOrigin, cookieOptions } from "@/lib/security";
export async function POST(request: Request) {
 if (!trustedOrigin(request)) return NextResponse.json({detail:"Request origin rejected"},{status:403});
 const result=NextResponse.json({ok:true}); result.cookies.set(SESSION_COOKIE,"",{...cookieOptions(),maxAge:0}); return result;
}
