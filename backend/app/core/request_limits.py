"""Bound JSON bodies before framework parsing; retain valid API contracts."""
import json
from starlette.responses import JSONResponse

MAX_BODY_BYTES = 65536


class RequestLimits:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await self.app(scope, receive, send)

        async def reject(code, message):
            await JSONResponse({"detail": message}, status_code=code,
                               headers={"Cache-Control": "private, no-store"})(scope, receive, send)

        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
            if declared < 0:
                raise ValueError()
        except ValueError:
            return await reject(400, "Invalid request length")
        if declared > MAX_BODY_BYTES:
            return await reject(413, "Request body exceeds 65536 bytes")
        body = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue
            chunk = event.get("body", b"")
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                return await reject(413, "Request body exceeds 65536 bytes")
            body.extend(chunk)
            if not event.get("more_body", False):
                break
        media = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
        if body and (not media or media == b"application/json" or media.endswith(b"+json")):
            try:
                json.loads(body)
            except (ValueError, RecursionError):
                return await reject(422, "Malformed JSON request")
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
