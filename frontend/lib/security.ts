export const SESSION_COOKIE = "flowforge_reviewer";
export function trustedOrigin(request: Request): boolean {
  const expected = process.env.DASHBOARD_ORIGIN || "http://localhost:3000";
  return request.headers.get("origin") === expected &&
    !["cross-site", "none"].includes(request.headers.get("sec-fetch-site") || "") &&
    request.headers.get("content-type")?.split(";")[0] === "application/json";
}
export function backendUrl(path: string) {
  return (process.env.BACKEND_URL || "http://backend:8001") + "/api" + path;
}
export const cookieOptions = () => ({
  httpOnly: true, sameSite: "strict" as const, secure: process.env.COOKIE_SECURE === "true",
  path: "/", maxAge: 3600,
});
