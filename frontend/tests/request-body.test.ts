import {describe,it,expect,vi,afterEach} from "vitest";
import {readJsonBody,RequestBodyError} from "@/lib/request-body";
import {POST as login} from "@/app/api/auth/login/route";
import {POST as decide} from "@/app/api/reviews/[id]/[decision]/route";
import {POST as generate} from "@/app/api/digests/generate/route";
vi.mock("next/headers",()=>({cookies:async()=>({get:()=>({value:"synthetic-token"})})}));
const headers={origin:"http://localhost:3000","content-type":"application/json"};
function request(body:string,extra:Record<string,string>={}){
 return new Request("http://localhost:3000/api/test",{method:"POST",headers:{...headers,...extra},body});
}
afterEach(()=>vi.unstubAllGlobals());
describe("actual request byte boundaries",()=>{
 it("accepts the inclusive byte limit",async()=>{
  const raw=JSON.stringify({a:"é"});const size=new TextEncoder().encode(raw).length;
  await expect(readJsonBody(request(raw),size)).resolves.toEqual({a:"é"});
  await expect(readJsonBody(request(raw),size-1)).rejects.toMatchObject({status:413});
 });
 it("rejects lying and missing Content-Length",async()=>{
  for(const extra of [{},{"content-length":"1"}] as Record<string,string>[])
   await expect(readJsonBody(request('{"a":"'+ "x".repeat(5000)+'"}',extra),4096)).rejects.toMatchObject({status:413});
 });
 it("cancels an oversized chunked reader",async()=>{
  const cancel=vi.fn();const body=new ReadableStream({start(c){c.enqueue(new Uint8Array(4097));},cancel});
  const req=new Request("http://localhost/api/test",{method:"POST",body,duplex:"half"} as RequestInit);
  await expect(readJsonBody(req,4096)).rejects.toBeInstanceOf(RequestBodyError);
  expect(cancel).toHaveBeenCalledOnce();
 });
 it.each(["null","[]",'{"private":"CANARY",',""])( "rejects invalid/non-object JSON: %s",async raw=>{
  await expect(readJsonBody(request(raw),4096)).rejects.toMatchObject({status:422,message:"Use a valid JSON object"});
 });
});
describe("server route errors before backend forwarding",()=>{
 it("login rejects streamed oversize without calling backend",async()=>{
  const fetch=vi.fn();vi.stubGlobal("fetch",fetch);
  expect((await login(request('{"username":[],"password":[],"extra":"'+"x".repeat(5000)+'"}'))).status).toBe(413);
  expect(fetch).not.toHaveBeenCalled();
 });
 it("login reports malformed JSON as a client error",async()=>{
  const response=await login(request('{"private":"CANARY",'));
  expect(response.status).toBe(422);expect(await response.text()).not.toContain("CANARY");
 });
 it("decision rejects oversize and malformed JSON before forwarding",async()=>{
  const fetch=vi.fn();vi.stubGlobal("fetch",fetch);
  const context={params:Promise.resolve({id:"a".repeat(36),decision:"approve"})};
  expect((await decide(request('{"x":"'+"x".repeat(5000)+'"}'),context)).status).toBe(413);
  expect((await decide(request("{"),context)).status).toBe(422);
  expect(fetch).not.toHaveBeenCalled();
 });
 it("digest counts UTF-8 bytes before forwarding",async()=>{
  const fetch=vi.fn();vi.stubGlobal("fetch",fetch);
  expect((await generate(request('{"x":"'+"é".repeat(600)+'"}'))).status).toBe(413);
  expect(fetch).not.toHaveBeenCalled();
 });
});
