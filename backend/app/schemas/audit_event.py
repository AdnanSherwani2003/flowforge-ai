from datetime import datetime
from typing import Dict, Any, List
from pydantic import BaseModel, ConfigDict


class AuditEventResponse(BaseModel):
    id: str
    entity_id: str
    event_type: str
    actor: str
    timestamp: datetime
    safe_detail: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class TicketAuditResponse(BaseModel):
    ticket_id: str
    audit_events: List[AuditEventResponse]
