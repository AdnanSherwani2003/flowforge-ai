import { test, expect } from "vitest";
import { trustedOrigin, cookieOptions } from "@/lib/security";
const request=(origin:string,site="same-origin",content="application/json")=>new Request("http://localhost:3000/api/auth/login",{method:"POST",headers:{origin,"sec-fetch-site":site,"content-type":content}});
test("same-origin JSON mutations are allowed",()=>{expect(trustedOrigin(request("http://localhost:3000"))).toBe(true);});
test("cross-origin mutation is rejected",()=>{expect(trustedOrigin(request("http://localhost:4444"))).toBe(false);});
test("forged cross-site metadata is rejected",()=>{expect(trustedOrigin(request("http://localhost:3000","cross-site"))).toBe(false);});
test("missing origin and non-JSON forms are rejected",()=>{expect(trustedOrigin(new Request("http://localhost:3000"))).toBe(false);expect(trustedOrigin(request("http://localhost:3000","same-origin","application/x-www-form-urlencoded"))).toBe(false);});
test("session cookie is HttpOnly and strictly same-site",()=>{expect(cookieOptions()).toEqual(expect.objectContaining({httpOnly:true,sameSite:"strict",path:"/",maxAge:3600}));});
