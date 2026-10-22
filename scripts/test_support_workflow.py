#!/usr/bin/env python3
"""Compatibility entrypoint for normal-operation webhook acceptance.

Fault injection lives in test_workflow_faults.py and never enables business hooks.
"""
import json
import urllib.error
import urllib.request

N8N_WEBHOOK_URL = "http://localhost:5679/webhook/support-ticket-intake"
BACKEND_URL = "http://localhost:8001"
_NO_BODY = object()


def make_request(url, method="GET", data=_NO_BODY, headers=None, timeout=12.0):
    headers = dict(headers or {})
    encoded = None
    if data is not _NO_BODY:
        encoded = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, dict(response.headers), json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"error": "Non-JSON HTTP response"}
        return exc.code, dict(exc.headers), parsed
    except Exception as exc:
        return 0, {}, {"error": type(exc).__name__}


def run_tests():
    from test_normal_workflow import main
    main()
    return True


if __name__ == "__main__":
    run_tests()
