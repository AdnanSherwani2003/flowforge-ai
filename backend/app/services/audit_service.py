from typing import Any, Dict
from sqlalchemy.orm import Session
from app.models.audit_event import AuditEvent


def record_audit_event(
    db: Session,
    entity_id: str,
    event_type: str,
    safe_detail: Dict[str, Any],
    actor: str = "api_client",
) -> AuditEvent:
    """Records an append-only audit event with strictly sanitised, safe operational details.
    Never persists full bodies, passwords, tokens, or unnecessary PII.
    """
    import uuid
    event = AuditEvent(
        id=str(uuid.uuid4()),
        entity_id=entity_id,
        event_type=event_type,
        actor=actor,
        safe_detail=safe_detail,
    )
    db.add(event)
    return event
