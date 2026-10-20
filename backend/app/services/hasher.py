import hashlib
import json
from typing import Any, Dict


def compute_canonical_hash(payload: Dict[str, Any]) -> str:
    """Computes SHA-256 hash of a canonically formatted JSON dictionary.
    Keys are sorted, whitespace minimized, strings trimmed.
    """
    cleaned: Dict[str, Any] = {}
    for k, v in payload.items():
        if isinstance(v, str):
            cleaned[k] = v.strip()
        else:
            cleaned[k] = v

    canonical_json = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
