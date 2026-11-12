from __future__ import annotations
from fastapi import APIRouter, Depends
from backend.core.dependencies import get_current_user
from backend.services.paypal import get_connection_status

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/paypal/status")
async def paypal_status(current_user=Depends(get_current_user)):
    return get_connection_status()
