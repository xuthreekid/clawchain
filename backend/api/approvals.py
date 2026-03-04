"""POST /api/approvals/{id}/resolve — 用户确认/拒绝危险工具执行"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from graph.approval_store import approval_store

router = APIRouter()


class ResolveRequest(BaseModel):
    decision: str  # "approved" | "denied"


@router.post("/approvals/{approval_id}/resolve")
async def resolve_approval(approval_id: str, body: ResolveRequest):
    """用户确认或拒绝待执行的危险工具"""
    decision = (body.decision or "").strip().lower()
    if decision not in ("approved", "denied"):
        raise HTTPException(400, "decision 必须为 approved 或 denied")

    ok = approval_store.resolve(approval_id, decision)
    if not ok:
        raise HTTPException(404, "approval_id 不存在或已超时")
    return {"ok": True, "decision": decision}
