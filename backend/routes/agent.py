from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db_session
from backend.core.dependencies import get_current_user
from backend.core.exceptions import AppException
from backend.services.ai_agent import process_agent_command
from backend.services.invoice import create_invoice_draft
from backend.schemas.agent import AgentCommandRequest, AgentResponse
from backend.schemas.invoice import InvoiceDraftRequest, LineItemRequest
from backend.models.audit import AuditLog, AuditAction
from datetime import date, timedelta
from decimal import Decimal
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/commands", response_model=AgentResponse)
async def agent_command(
    req: AgentCommandRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        result = await process_agent_command(
            message=req.message,
            session_id=req.session_id,
            conversation_history=req.conversation_history,
        )
        # Audit the AI command
        audit = AuditLog(
            user_id=current_user.id,
            action=AuditAction.AI_COMMAND.value,
            description=f"AI command processed, session={result.session_id}",
            metadata_={"session_id": result.session_id, "ready": result.ready_for_review},
        )
        db.add(audit)
        await db.commit()
        return result
    except AppException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
