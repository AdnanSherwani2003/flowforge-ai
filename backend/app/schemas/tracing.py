"""Shared contracts for identifiers persisted in audit JSON and VARCHAR(100) telemetry."""
from typing import Annotated
from pydantic import StringConstraints

# ASCII identifiers can safely round-trip through HTTP headers without normalization.
TraceId = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._:-]+$"),
]
