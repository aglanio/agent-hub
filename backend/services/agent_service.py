"""Servico de agentes — leitura de SKILL.md, reports, dados JSON."""

import json
from pathlib import Path
from backend.config import IS_VPS, TASKS_DIR, REPORTS_DIR, OPENCLAW_SKILLS_DIR, NANOCLAW_DIR, DATA_DIR


def _load_json(filename: str):
    p = DATA_DIR / filename
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def get_agents_data():
    return _load_json("agents.json")


def get_projects_data():
    return _load_json("projects.json")


def parse_frontmatter(content: str) -> dict:
    fm = {}
    if content.startswith("---"):
        for line in content.split("\n")[1:]:
            if line.startswith("---"):
                break
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')
    return fm


def read_skill(aid: str) -> str:
    if IS_VPS or TASKS_DIR is None:
        # Na VPS, retorna config embutida dos vps_agents
        data = get_agents_data()
        for cfg in data.get("vps_agents", []):
            if cfg["id"] == aid:
                return f"# {cfg['name']}\n\n{cfg['description']}\n\nSchedule: {cfg.get('schedule', 'N/A')}"
        return ""
    p = TASKS_DIR / aid / "SKILL.md"
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""


def read_report(aid: str):
    if REPORTS_DIR is None:
        return None
    if IS_VPS:
        REPORTS_DIR.mkdir(exist_ok=True)
    p = REPORTS_DIR / f"{aid}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


def save_report(aid: str, data: dict):
    if REPORTS_DIR is None:
        return
    REPORTS_DIR.mkdir(exist_ok=True)
    p = REPORTS_DIR / f"{aid}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_agents() -> dict:
    data = get_agents_data()
    layout = data.get("layout", {})
    virtual_nodes = data.get("virtual_nodes", [])
    connections = data.get("connections", [])
    projects = get_projects_data()

    agents = []

    if IS_VPS:
        # VPS: usa dados embutidos
        for cfg in data.get("vps_agents", []):
            report = read_report(cfg["id"])
            agents.append({
                "id": cfg["id"],
                "name": cfg["name"],
                "description": cfg["description"],
                "icon": cfg["icon"],
                "color": cfg["color"],
                "x": cfg["x"],
                "y": cfg["y"],
                "schedule": cfg.get("schedule", ""),
                "has_report": report is not None,
                "last_run": report.get("hora") if report else None,
                "report_date": report.get("data") if report else None,
                "virtual": False,
            })
    else:
        # Local: le SKILL.md dos agentes agendados
        if TASKS_DIR and TASKS_DIR.exists():
            for sp in sorted(TASKS_DIR.glob("*/SKILL.md")):
                aid = sp.parent.name
                if aid.startswith("."):
                    continue
                content = read_skill(aid)
                fm = parse_frontmatter(content)
                report = read_report(aid)
                lay = layout.get(aid, {
                    "x": 200, "y": 200, "color": "#6b7280",
                    "icon": "\ud83e\udd16",
                    "label": aid.replace("agente-", "").replace("-", " ").title()
                })
                agents.append({
                    "id": aid,
                    "name": lay.get("label", fm.get("name", aid)),
                    "description": fm.get("description", "Agente agendado"),
                    "icon": lay["icon"],
                    "color": lay["color"],
                    "x": lay["x"],
                    "y": lay["y"],
                    "schedule": fm.get("schedule", ""),
                    "has_report": report is not None,
                    "last_run": report.get("hora") if report else None,
                    "report_date": report.get("data") if report else None,
                    "virtual": False,
                })

    agents.extend(virtual_nodes)
    agents.extend(projects)
    return {"agents": agents, "connections": connections}


def categorize_skill(name: str) -> str:
    if name.startswith("bio-"):
        return "Bioinformatics"
    elif name.startswith("tooluniverse-"):
        return "ToolUniverse"
    elif name.startswith("single-"):
        return "Single-Cell"
    elif name.startswith("bulk-"):
        return "Bulk Analysis"
    elif "drug" in name or "chem" in name or "pharma" in name:
        return "Drug Discovery"
    elif "clinical" in name or "medical" in name or "health" in name:
        return "Clinical/Medical"
    elif "cancer" in name or "tumor" in name or "oncology" in name:
        return "Oncology"
    elif "protein" in name or "antibody" in name:
        return "Protein/Structure"
    elif "agent" in name:
        return "AI Agents"
    elif "data" in name or "stats" in name or "viz" in name:
        return "Data/Visualization"
    return "Other"


def list_skill_packs() -> dict:
    packs = []

    if IS_VPS:
        # VPS: dados estaticos
        packs.append({
            "id": "openclaw-medical",
            "name": "OpenClaw Medical Skills",
            "description": "869 skills medicas/cientificas -- Genomica, Bioinformatica, Drug Discovery, IA Clinica",
            "total_skills": 869,
            "categories": {
                "Bioinformatics": 380, "ToolUniverse": 120, "Single-Cell": 45,
                "Drug Discovery": 80, "Clinical/Medical": 60, "Oncology": 40,
                "Protein/Structure": 35, "AI Agents": 25, "Other": 84,
            },
            "source": "FreedomIntelligence/OpenClaw-Medical-Skills",
            "installed": True,
        })
    else:
        # Local: escaneia diretorio
        openclaw_count = 0
        openclaw_categories = {}
        if OPENCLAW_SKILLS_DIR and OPENCLAW_SKILLS_DIR.exists():
            for skill_dir in sorted(OPENCLAW_SKILLS_DIR.iterdir()):
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    openclaw_count += 1
                    cat = categorize_skill(skill_dir.name)
                    openclaw_categories[cat] = openclaw_categories.get(cat, 0) + 1
        packs.append({
            "id": "openclaw-medical",
            "name": "OpenClaw Medical Skills",
            "description": "869 skills medicas/cientificas -- Genomica, Bioinformatica, Drug Discovery, IA Clinica",
            "total_skills": openclaw_count,
            "categories": openclaw_categories,
            "source": "FreedomIntelligence/OpenClaw-Medical-Skills",
            "installed": True,
            "path": str(OPENCLAW_SKILLS_DIR) if OPENCLAW_SKILLS_DIR else None,
        })

    # NanoClaw pack
    nanoclaw_installed = NANOCLAW_DIR.exists() if NANOCLAW_DIR else False
    packs.append({
        "id": "nanoclaw",
        "name": "NanoClaw",
        "description": "Assistente IA pessoal multi-canal -- WhatsApp, Telegram, Discord, Slack, Gmail",
        "total_skills": 22,
        "categories": {"Channels": 8, "Setup": 3, "Integrations": 5, "Voice/Media": 3, "Management": 3},
        "source": "qwibitai/nanoclaw",
        "installed": nanoclaw_installed,
        "path": str(NANOCLAW_DIR) if NANOCLAW_DIR else None,
        "features": [
            "WhatsApp integration", "Telegram bot", "Discord bot",
            "Slack channel", "Gmail integration", "Voice transcription (Whisper)",
            "Agent Swarms", "Docker sandboxes", "Scheduled tasks",
            "X/Twitter posting", "PDF reading", "Image vision",
        ],
    })
    return {"packs": packs}


def list_pack_skills(pack_id: str, category: str = None, search: str = None) -> dict:
    skills = []
    if pack_id == "openclaw-medical" and OPENCLAW_SKILLS_DIR and OPENCLAW_SKILLS_DIR.exists():
        for skill_dir in sorted(OPENCLAW_SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            name = skill_dir.name
            cat = categorize_skill(name)
            if category and cat != category:
                continue
            if search and search.lower() not in name.lower():
                continue
            try:
                content = skill_file.read_text(encoding="utf-8", errors="ignore")[:500]
                fm = parse_frontmatter(content)
                desc = fm.get("description", name.replace("-", " ").replace("bio ", "").title())
            except Exception:
                desc = name.replace("-", " ").title()
            skills.append({"id": name, "name": name, "category": cat, "description": desc})
    return {"skills": skills, "total": len(skills)}
