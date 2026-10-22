import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { backendUrl, SESSION_COOKIE } from "./security";
export async function backend<T>(path: string): Promise<T> {
 const token = (await cookies()).get(SESSION_COOKIE)?.value;
 if (!token) redirect("/login");
 const response = await fetch(backendUrl(path), {
  headers: {Authorization: "Bearer " + token}, cache: "no-store", signal: AbortSignal.timeout(8000)
 });
 if (response.status === 401) redirect("/login?expired=1");
 if (!response.ok) throw new Error("The review service could not load this request. Please refresh.");
 return response.json();
}
