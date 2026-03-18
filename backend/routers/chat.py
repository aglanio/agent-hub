"""Router de chat — conversa com agentes via Anthropic."""

from fastapi import APIRouter
from backend.models import ChatMsg
from backend.services.chat_service import send_message, get_history, clear_history

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/chat")
def chat(body: ChatMsg):
    reply = send_message(body.agent_id, body.message)
    return {"reply": reply}


@router.get("/chat/{aid}/history")
def history(aid: str):
    return get_history(aid)


@router.delete("/chat/{aid}/history")
def delete_history(aid: str):
    clear_history(aid)
    return {"ok": True}
