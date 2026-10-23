/** Count actual bytes, including chunked requests without Content-Length. */
export class RequestBodyError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export async function readJsonBody(request: Request, limit: number): Promise<Record<string, unknown>> {
  const declared = request.headers.get("content-length");
  if (declared !== null && (!/^\d+$/.test(declared) || !Number.isSafeInteger(Number(declared))))
    throw new RequestBodyError(400, "Invalid request length");
  if (declared !== null && Number(declared) > limit)
    throw new RequestBodyError(413, "Request too large");
  const reader = request.body?.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    if (reader) {
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > limit) throw new RequestBodyError(413, "Request too large");
        chunks.push(value);
      }
    }
  } catch (error) {
    await reader?.cancel().catch(() => {});
    throw error;
  } finally { reader?.releaseLock(); }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  try {
    const value = JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(bytes));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error();
    return value;
  } catch { throw new RequestBodyError(422, "Use a valid JSON object"); }
}
