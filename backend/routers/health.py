"""Router de health checks — status de servicos externos."""

import httpx
from fastapi import APIRouter
from backend.config import IS_VPS, NANOCLAW_DIR, ROUTE_AGENT_PATH

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/route-agent/status")
async def route_agent_status():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://localhost:8000/health")
            return {"running": True, "data": resp.json(), "url": "http://localhost:3000"}
    except Exception:
        return {
            "running": False,
            "url": "http://localhost:3000",
            "path": str(ROUTE_AGENT_PATH) if ROUTE_AGENT_PATH else None,
        }


@router.get("/nanoclaw/status")
async def nanoclaw_status():
    installed = NANOCLAW_DIR.exists() if NANOCLAW_DIR else False
    return {
        "installed": installed,
        "path": str(NANOCLAW_DIR) if NANOCLAW_DIR else None,
        "channels": ["WhatsApp (Baileys)", "Telegram", "Discord", "Slack", "Gmail", "X/Twitter"],
        "features": [
            "Voice Transcription (Whisper)", "Image Vision", "PDF Reader",
            "Agent Swarms", "Docker Sandboxes",
        ],
    }


@router.get("/email-agent/status")
async def email_agent_status():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://localhost:8090/api/status")
            return {"running": True, "data": resp.json(), "url": "http://localhost:8090"}
    except Exception:
        return {"running": False, "url": "http://localhost:8090"}
