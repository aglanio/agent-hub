"""Router de skill packs — OpenClaw, NanoClaw."""

from fastapi import APIRouter
from backend.services.agent_service import list_skill_packs, list_pack_skills

router = APIRouter(prefix="/api", tags=["skills"])


@router.get("/skill-packs")
def get_skill_packs():
    return list_skill_packs()


@router.get("/skill-packs/{pack_id}/skills")
def get_pack_skills(pack_id: str, category: str = None, search: str = None):
    return list_pack_skills(pack_id, category, search)
