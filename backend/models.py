"""Pydantic models para validacao de requests."""

from pydantic import BaseModel


class ChatMsg(BaseModel):
    agent_id: str
    message: str
