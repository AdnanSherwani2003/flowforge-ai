"""Bounded local inference. Untrusted text and model output never execute code."""
import asyncio
import json
import re
import time
from dataclasses import dataclass
from contextlib import AsyncExitStack

import httpx
from pydantic import ValidationError
from app.core.config import settings
from app.prompts.support_ticket_v1 import SYSTEM_PROMPT
from app.schemas.enrichment import ModelSuggestion

MAX_RESPONSE_BYTES = 65536
INJECTION_MARKERS = re.compile(
    r"(?:ignore|disregard|override).{0,60}(?:instructions|prompt|system)"
    r"|(?:^|\n)\s*(?:system|developer|assistant)\s*:"
    r"|<\|(?:im_start|system)\|>|reveal.{0,30}(?:system|prompt)",
    re.IGNORECASE,
)
_GATE = asyncio.Semaphore(1)
REASONS = {
    "billing": "A payment, invoice or refund issue merits a billing review.",
    "account_access": "An authentication or access issue merits an account review.",
    "technical_issue": "A software or service issue merits a technical review.",
    "shipping": "A delivery issue merits a shipping review.",
    "general": "An informational question merits a general support review.",
}


@dataclass(frozen=True)
class InferenceOutcome:
    status: str
    diagnostic_code: str
    category: str = "unknown"
    priority: str = "unknown"
    reason: str = "AI enrichment is unavailable. Manual review is needed."
    confidence: float | None = None
    duration_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class UpstreamFailure(Exception):
    def __init__(self, code):
        self.code = code


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


async def _bounded_json(client, method, path, payload=None):
    async with client.stream(method, settings.OLLAMA_BASE_URL + path, json=payload) as response:
        if response.status_code != 200:
            raise UpstreamFailure("model_missing" if response.status_code == 404 else "upstream_error")
        length = response.headers.get("content-length")
        if length and (not length.isdigit() or int(length) > MAX_RESPONSE_BYTES):
            raise UpstreamFailure("response_too_large")
        data = bytearray()
        async for chunk in response.aiter_bytes(chunk_size=8192):
            data.extend(chunk)
            if len(data) > MAX_RESPONSE_BYTES:
                raise UpstreamFailure("response_too_large")
        try:
            value = json.loads(data, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise UpstreamFailure("invalid_response") from None
        if not isinstance(value, dict):
            raise UpstreamFailure("invalid_response")
        return value


def _counter(value):
    return value if type(value) is int and 0 <= value <= 10_000_000 else None


async def classify_ticket(subject, body, *, client=None):
    started = time.monotonic()

    def outcome(status, code, **kwargs):
        return InferenceOutcome(status, code, duration_ms=round((time.monotonic() - started) * 1000), **kwargs)

    if not settings.ENRICHMENT_ENABLED:
        return outcome("unavailable", "disabled")
    if len(subject) + len(body) > settings.ENRICHMENT_MAX_INPUT_CHARS:
        return outcome("needs_review", "input_too_long", reason="Ticket exceeds the AI input bound. Manual review is needed.")
    if INJECTION_MARKERS.search(subject + "\n" + body):
        return outcome("needs_review", "suspicious_input", reason="Potential instruction content requires manual review.")

    acquired = False
    try:
        try:
            await asyncio.wait_for(_GATE.acquire(), timeout=0.1)
            acquired = True
        except TimeoutError:
            return outcome("unavailable", "busy")
        # One deadline covers metadata requests, inference, decoding and validation.
        async with asyncio.timeout(settings.OLLAMA_TIMEOUT_SECONDS):
            async with AsyncExitStack() as stack:
                if client is None:
                    client = await stack.enter_async_context(httpx.AsyncClient(
                        timeout=httpx.Timeout(settings.OLLAMA_TIMEOUT_SECONDS, connect=2),
                        follow_redirects=False, trust_env=False,
                    ))
                tags = await _bounded_json(client, "GET", "/api/tags")
                matches = [m for m in tags.get("models", []) if isinstance(m, dict) and m.get("name") == settings.OLLAMA_MODEL]
                if len(matches) != 1:
                    raise UpstreamFailure("model_missing")
                metadata = matches[0]
                if metadata.get("remote_host") or metadata.get("remote_model"):
                    raise UpstreamFailure("remote_model_blocked")
                if metadata.get("digest") != settings.OLLAMA_MODEL_DIGEST:
                    raise UpstreamFailure("model_digest_mismatch")
                options = {"temperature": 0, "seed": 42, "num_ctx": 2048, "num_predict": 160}
                if settings.OLLAMA_NUM_GPU >= 0:
                    options["num_gpu"] = settings.OLLAMA_NUM_GPU
                payload = {
                    "model": settings.OLLAMA_MODEL, "stream": False,
                    "format": ModelSuggestion.model_json_schema(), "options": options, "keep_alive": "2m",
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps({"untrusted_ticket": {"subject": subject, "body": body}})},
                    ],
                }
                envelope = await _bounded_json(client, "POST", "/api/chat", payload)
                if (envelope.get("model") != settings.OLLAMA_MODEL or envelope.get("done") is not True
                        or envelope.get("done_reason") not in (None, "stop")):
                    raise UpstreamFailure("incomplete_response")
                message = envelope.get("message")
                if not isinstance(message, dict) or message.get("tool_calls") or message.get("role") != "assistant":
                    raise UpstreamFailure("invalid_response")
                try:
                    content = message.get("content")
                    if not isinstance(content, str) or len(content.encode()) > 4096:
                        raise ValueError("Invalid content")
                    parsed = ModelSuggestion.model_validate(json.loads(content, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant))
                except (ValidationError, ValueError, TypeError, RecursionError):
                    return outcome("needs_review", "invalid_output", reason="AI output failed validation. Manual review is needed.")
                if parsed.category == "unknown" or (parsed.confidence is not None and parsed.confidence < 0.65):
                    return outcome("needs_review", "abstained", reason="The AI suggestion is ambiguous. Manual review is needed.")
                # Model-written reason is validated and discarded: never persist copied customer text.
                return outcome(
                    "succeeded", "validated", category=parsed.category, priority=parsed.priority,
                    reason=REASONS[parsed.category], confidence=parsed.confidence,
                    prompt_tokens=_counter(envelope.get("prompt_eval_count")),
                    completion_tokens=_counter(envelope.get("eval_count")),
                )
    except (TimeoutError, httpx.TimeoutException):
        return outcome("unavailable", "timeout")
    except httpx.RequestError:
        return outcome("unavailable", "unreachable")
    except UpstreamFailure as error:
        return outcome("unavailable", error.code)
    except (ValueError, TypeError, KeyError):
        return outcome("unavailable", "invalid_response")
    finally:
        if acquired:
            _GATE.release()
