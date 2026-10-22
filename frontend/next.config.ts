import type { NextConfig } from "next";
const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() { return [{ source: "/:path*", headers: [
    { key: "Cache-Control", value: "private, no-store, max-age=0" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "no-referrer" },
    { key: "Content-Security-Policy", value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" }
  ] }]; }
};
export default config;
