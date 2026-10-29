import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlmodel import Session, select, desc
from database import engine
from models import AuditLogEntry, ConfidenceLevel

def record_audit_event(
    event_type: str,
    task_title: str,
    target_employee_id: Optional[str] = None,
    ai_confidence: Optional[ConfidenceLevel] = None,
    details: Optional[Dict[str, Any]] = None,
    manager_decision: Optional[str] = None,
    session: Optional[Session] = None
) -> AuditLogEntry:
    """Appends an immutable audit event to the system ledger in the SQLite database."""
    if session is None:
        with Session(engine) as local_session:
            return record_audit_event(
                event_type=event_type,
                task_title=task_title,
                target_employee_id=target_employee_id,
                ai_confidence=ai_confidence,
                details=details,
                manager_decision=manager_decision,
                session=local_session
            )

    entry = AuditLogEntry(
        log_id=f"AUDIT-{str(uuid.uuid4())[:8].upper()}",
        timestamp=datetime.now(),
        event_type=event_type,
        task_title=task_title,
        target_employee_id=target_employee_id,
        ai_confidence=ai_confidence,
        details=details or {},
        manager_decision=manager_decision
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry

def get_audit_logs(session: Optional[Session] = None) -> List[AuditLogEntry]:
    """Retrieves all logged system events in reverse chronological order."""
    if session is None:
        with Session(engine) as local_session:
            return get_audit_logs(session=local_session)

    statement = select(AuditLogEntry).order_by(desc(AuditLogEntry.timestamp))
    return list(session.exec(statement).all())