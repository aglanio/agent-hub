"""Router de agentes — CRUD, reports, skills."""

from fastapi import APIRouter, Request, HTTPException
from backend.config import IS_VPS, REPORT_UPLOAD_TOKEN
from backend.services.agent_service import (
    list_agents,
    read_report,
    read_skill,
    save_report,
)

router = APIRouter(prefix="/api", tags=["agents"])


@router.get("/agents")
def get_agents():
    return list_agents()


@router.get("/agents/{aid}/report")
def get_report(aid: str):
    r = read_report(aid)
    return r if r else {"error": "Relatorio nao encontrado"}


@router.get("/agents/{aid}/skill")
def get_skill(aid: str):
    return {"content": read_skill(aid)}


# Upload report endpoint (VPS only — local machine pushes reports here)
if IS_VPS:
    @router.post("/agents/{aid}/report")
    async def upload_report(aid: str, data: dict, request: Request):
        token = request.headers.get("x-report-token", "")
        if not REPORT_UPLOAD_TOKEN or token != REPORT_UPLOAD_TOKEN:
            raise HTTPException(status_code=401, detail="Invalid or missing report token")
        safe_aid = "".join(c for c in aid if c.isalnum() or c in "-_")
        if not safe_aid or safe_aid != aid:
            raise HTTPException(status_code=400, detail="Invalid agent ID")
        save_report(safe_aid, data)
        return {"ok": True}
