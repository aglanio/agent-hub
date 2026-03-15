from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, json, os, httpx, asyncio
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

BASE_DIR   = Path(__file__).parent
DB_PATH    = BASE_DIR / "data" / "hub.db"
REPORTS_DIR = Path(r"C:\Users\aglan\.claude\agent-reports")
TASKS_DIR  = Path(r"C:\Users\aglan\.claude\scheduled-tasks")

# Posições e estilos dos nós no canvas
LAYOUT = {
    "agente-desenvolvimento":         {"x":350,"y":30, "color":"#3b82f6","icon":"🛠️","label":"Desenvolvimento"},
    "agente-estrategico-noite":       {"x":700,"y":30, "color":"#8b5cf6","icon":"🌙","label":"Noturno"},
    "agente-estrategico-manha":       {"x":50, "y":30, "color":"#f59e0b","icon":"🌅","label":"Manhã"},
    "inspecao-geral-sistemas":        {"x":50, "y":220,"color":"#10b981","icon":"🔍","label":"Inspeção Sistemas"},
    "verificador-publicacoes":        {"x":350,"y":220,"color":"#06b6d4","icon":"📡","label":"Verificador Publicações"},
    "atualizacao-deploy-verificacao": {"x":700,"y":220,"color":"#ef4444","icon":"🚀","label":"Deploy & Verificação"},
    "manutencao-correcao-sistemas":   {"x":50, "y":410,"color":"#f97316","icon":"🔧","label":"Manutenção & Correção"},
}

VIRTUAL_NODES = [
    {"id":"_whatsapp",    "name":"WhatsApp",    "icon":"📱","color":"#22c55e","x":1000,"y":30,"virtual":True},
    {"id":"_vps",         "name":"VPS Reports", "icon":"💾","color":"#ef4444","x":1000,"y":220,"virtual":True},
    {"id":"_route_agent", "name":"Route Agent", "icon":"🗺️","color":"#0ea5e9","x":1000,"y":410,"virtual":True,
     "url":"http://localhost:3000", "api":"http://localhost:8000/health",
     "description":"Agente IA de Rotas: OR-Tools + ORS + HERE Traffic"},
    {"id":"_nanoclaw",    "name":"NanoClaw",    "icon":"🐾","color":"#ec4899","x":350,"y":410,"virtual":False,
     "description":"Assistente IA Multi-Canal: WhatsApp (Baileys), Telegram, Discord, Slack, Gmail",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "sempre ativo",
     "channels": ["WhatsApp","Telegram","Discord","Slack","Gmail","X/Twitter"],
     "features": ["Voice Transcription","Image Vision","PDF Reader","Agent Swarms","Docker Sandboxes"]},
    {"id":"_email_agent", "name":"Email TRF1",  "icon":"📧","color":"#f59e0b","x":700,"y":410,"virtual":False,
     "description":"Automação PJe + Outlook: upload PDFs, extrai dados, cria rascunhos, escritório virtual IA",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "sob demanda",
     "url": "http://localhost:8090"},
]

# ── Projetos Extras (extraídos dos zips) ──────────────────────────────────
PROJECTS_DIR = Path(r"C:\Users\aglan\OneDrive\Documentos\claude projetos\projetos-extras")

EXTRA_PROJECTS = [
    # Jurídico
    {"id":"_advocacia_demo", "name":"Advocacia Demo", "icon":"⚖️", "color":"#a855f7",
     "x":50, "y":630, "virtual":False, "category":"juridico",
     "description":"Site portfólio escritório advocacia — HTML5, CSS3, jQuery, Particles.js",
     "has_report":False, "last_run":None, "report_date":None, "schedule":"estático",
     "stack":"HTML5 + CSS3 + jQuery", "path":"advocacia-demo-master"},
    {"id":"_meuadvogado", "name":"MeuAdvogadoOnline", "icon":"👨‍⚖️", "color":"#6366f1",
     "x":300, "y":630, "virtual":False, "category":"juridico",
     "description":"SaaS LegalTech — Next.js 15 + React 19 + TypeScript + Tailwind + Framer Motion",
     "has_report":False, "last_run":None, "report_date":None, "schedule":"SaaS",
     "stack":"Next.js 15 + React 19 + TS", "path":"meuadvogadoonline--main"},
    # Finanças
    {"id":"_cfo", "name":"CFO Automatizado", "icon":"💰", "color":"#10b981",
     "x":550, "y":630, "virtual":False, "category":"financas",
     "description":"CFO automatizado — Node.js + Express + Vue 3 + NeDB + Keycloak",
     "has_report":False, "last_run":None, "report_date":None, "schedule":"full-stack",
     "stack":"Node.js + Vue 3 + TS", "path":"cfo-master"},
    {"id":"_cloud_roi", "name":"Cloud ROI Simulator", "icon":"☁️", "color":"#0ea5e9",
     "x":800, "y":630, "virtual":False, "category":"financas",
     "description":"Simulador ROI Cloud — framework decisão para negociação AWS ($5.4M)",
     "has_report":False, "last_run":None, "report_date":None, "schedule":"simulação",
     "stack":"Python", "path":"Cloud-Commitment-ROI-Simulator-main"},
    {"id":"_erp_analytics", "name":"ERP Analytics", "icon":"📊", "color":"#f43f5e",
     "x":1050, "y":630, "virtual":False, "category":"financas",
     "description":"Dashboard financeiro ERP — FastAPI + Streamlit + PostgreSQL + Plotly + ML",
     "has_report":False, "last_run":None, "report_date":None, "schedule":"plataforma",
     "stack":"FastAPI + Streamlit + PG", "path":"erp-financial-analytics-main"},
    # AI & Analytics
    {"id":"_500_agents", "name":"500 AI Agents", "icon":"🤖", "color":"#8b5cf6",
     "x":50, "y":820, "virtual":False, "category":"ai",
     "description":"Coleção 500+ projetos IA — CrewAI, AutoGen, Agno, LangGraph por indústria",
     "has_report":False, "last_run":None, "report_date":None, "schedule":"referência",
     "stack":"Python + JS frameworks", "path":"500-AI-Agents-Projects-main"},
    {"id":"_multicab_bi", "name":"MultiCab BI", "icon":"📈", "color":"#14b8a6",
     "x":300, "y":820, "virtual":False, "category":"analytics",
     "description":"Framework BI governance — snapshots T+3/T+7 para marketplaces multi-plataforma",
     "has_report":False, "last_run":None, "report_date":None, "schedule":"framework",
     "stack":"Metodologia + Docs", "path":"Marketplace-MultiCab-BI-Case-main"},
]

CONNECTIONS = [
    {"from":"agente-estrategico-manha",  "to":"agente-desenvolvimento",   "label":"plano.json"},
    {"from":"agente-estrategico-manha",  "to":"agente-estrategico-noite", "label":"metas"},
    {"from":"agente-desenvolvimento",    "to":"agente-estrategico-noite", "label":"dev-report.json"},
    {"from":"agente-desenvolvimento",    "to":"_whatsapp",                "label":"resumo dev"},
    {"from":"agente-estrategico-noite",  "to":"_whatsapp",                "label":"resumo noturno"},
    {"from":"agente-estrategico-noite",  "to":"_vps",                     "label":"noite.json"},
    {"from":"agente-desenvolvimento",    "to":"_route_agent",             "label":"rotas"},
    {"from":"_nanoclaw",                 "to":"_whatsapp",                "label":"Baileys WS"},
    {"from":"agente-desenvolvimento",    "to":"_nanoclaw",                "label":"multi-canal"},
    {"from":"_nanoclaw",                 "to":"_email_agent",             "label":"emails"},
    {"from":"agente-estrategico-manha",  "to":"_email_agent",             "label":"PJe diário"},
]

# Conexões dos projetos extras
CONNECTIONS.extend([
    {"from":"_email_agent",      "to":"_advocacia_demo", "label":"templates"},
    {"from":"_email_agent",      "to":"_meuadvogado",    "label":"LegalTech"},
    {"from":"agente-desenvolvimento", "to":"_cfo",       "label":"finanças"},
    {"from":"agente-desenvolvimento", "to":"_erp_analytics", "label":"analytics"},
    {"from":"_500_agents",       "to":"agente-desenvolvimento", "label":"referência"},
    {"from":"_cfo",              "to":"_cloud_roi",      "label":"ROI"},
    {"from":"_erp_analytics",    "to":"_multicab_bi",    "label":"BI data"},
])

ROUTE_AGENT_PATH = Path(r"C:\Users\aglan\OneDrive\Documentos\claude projetos\mapas\route-agent")
OPENCLAW_SKILLS_DIR = Path(r"C:\Users\aglan\.claude\skills")
NANOCLAW_DIR = Path(r"C:\Users\aglan\OneDrive\Documentos\claude projetos\agentes de ia claude\nanoclaw\nanoclaw-main")

app = FastAPI(title="Agent Hub")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    db = get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL, role TEXT NOT NULL,
        content TEXT NOT NULL,
        ts TEXT DEFAULT (datetime('now','localtime')))""")
    db.commit(); db.close()

@app.on_event("startup")
def startup(): init_db()

def read_skill(aid):
    p = TASKS_DIR / aid / "SKILL.md"
    return p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""

def read_report(aid):
    p = REPORTS_DIR / f"{aid}.json"
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except: pass
    return None

def parse_fm(content):
    fm = {}
    if content.startswith("---"):
        for line in content.split("\n")[1:]:
            if line.startswith("---"): break
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')
    return fm

@app.get("/api/agents")
def list_agents():
    agents = []
    if TASKS_DIR.exists():
        for sp in sorted(TASKS_DIR.glob("*/SKILL.md")):
            aid = sp.parent.name
            if aid.startswith("."): continue
            content = read_skill(aid)
            fm = parse_fm(content)
            report = read_report(aid)
            lay = LAYOUT.get(aid, {"x":200,"y":200,"color":"#6b7280","icon":"🤖","label":aid.replace("agente-","").replace("-"," ").title()})
            agents.append({
                "id": aid,
                "name": lay.get("label", fm.get("name", aid)),
                "description": fm.get("description","Agente agendado"),
                "icon": lay["icon"], "color": lay["color"],
                "x": lay["x"], "y": lay["y"],
                "schedule": fm.get("schedule",""),
                "has_report": report is not None,
                "last_run": report.get("hora") if report else None,
                "report_date": report.get("data") if report else None,
                "virtual": False
            })
    agents.extend(VIRTUAL_NODES)
    agents.extend(EXTRA_PROJECTS)
    return {"agents": agents, "connections": CONNECTIONS}

@app.get("/api/route-agent/status")
async def route_agent_status():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://localhost:8000/health")
            return {"running": True, "data": resp.json(), "url": "http://localhost:3000"}
    except:
        return {"running": False, "url": "http://localhost:3000", "path": str(ROUTE_AGENT_PATH)}

@app.get("/api/nanoclaw/status")
async def nanoclaw_status():
    return {
        "installed": NANOCLAW_DIR.exists(),
        "path": str(NANOCLAW_DIR),
        "channels": ["WhatsApp (Baileys)", "Telegram", "Discord", "Slack", "Gmail", "X/Twitter"],
        "features": ["Voice Transcription (Whisper)", "Image Vision", "PDF Reader", "Agent Swarms", "Docker Sandboxes"],
    }

@app.get("/api/email-agent/status")
async def email_agent_status():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://localhost:8090/api/status")
            return {"running": True, "data": resp.json(), "url": "http://localhost:8090"}
    except:
        return {"running": False, "url": "http://localhost:8090"}

@app.get("/api/agents/{aid}/report")
def get_report(aid: str):
    r = read_report(aid)
    return r if r else {"error": "Relatório não encontrado"}

@app.get("/api/agents/{aid}/skill")
def get_skill(aid: str):
    return {"content": read_skill(aid)}

class ChatMsg(BaseModel):
    agent_id: str
    message: str

@app.post("/api/chat")
def chat(body: ChatMsg):
    db = get_db()
    db.execute("INSERT INTO messages(agent_id,role,content) VALUES(?,?,?)", (body.agent_id,"user",body.message))
    db.commit()
    api_key = os.getenv("ANTHROPIC_API_KEY","")
    if api_key:
        try:
            import anthropic as ant
            skill = read_skill(body.agent_id)
            report = read_report(body.agent_id)
            system = (f"Você é o agente '{body.agent_id}', um agente autônomo de IA pessoal. "
                      f"Responda de forma concisa em português BR.\n\nSua configuração:\n{skill[:3000]}")
            if report:
                system += f"\n\nSeu último relatório:\n{json.dumps(report,ensure_ascii=False)[:1500]}"
            hist = db.execute(
                "SELECT role,content FROM messages WHERE agent_id=? ORDER BY id DESC LIMIT 20",
                (body.agent_id,)).fetchall()
            messages = [{"role":r["role"],"content":r["content"]} for r in reversed(hist)]
            client = ant.Anthropic(api_key=api_key)
            resp = client.messages.create(model="claude-3-5-haiku-20241022", max_tokens=1024,
                                          system=system, messages=messages)
            reply = resp.content[0].text
        except Exception as e:
            reply = f"❌ Erro API: {e}"
    else:
        reply = ("⚙️ Configure `ANTHROPIC_API_KEY` no arquivo `.env` para ativar o chat.\n\n"
                 "Posso mostrar seus relatórios e configurações mesmo sem a chave!")
    db.execute("INSERT INTO messages(agent_id,role,content) VALUES(?,?,?)", (body.agent_id,"assistant",reply))
    db.commit(); db.close()
    return {"reply": reply}

@app.get("/api/chat/{aid}/history")
def history(aid: str):
    db = get_db()
    rows = db.execute("SELECT role,content,ts FROM messages WHERE agent_id=? ORDER BY id", (aid,)).fetchall()
    db.close()
    return [dict(r) for r in rows]

@app.delete("/api/chat/{aid}/history")
def clear_history(aid: str):
    db = get_db()
    db.execute("DELETE FROM messages WHERE agent_id=?", (aid,))
    db.commit(); db.close()
    return {"ok": True}

@app.get("/api/skill-packs")
def list_skill_packs():
    packs = []
    # OpenClaw Medical Skills
    openclaw_count = 0
    openclaw_categories = {}
    if OPENCLAW_SKILLS_DIR.exists():
        for skill_dir in sorted(OPENCLAW_SKILLS_DIR.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                openclaw_count += 1
                name = skill_dir.name
                # Categorize by prefix
                if name.startswith("bio-"): cat = "Bioinformatics"
                elif name.startswith("tooluniverse-"): cat = "ToolUniverse"
                elif name.startswith("single-"): cat = "Single-Cell"
                elif name.startswith("bulk-"): cat = "Bulk Analysis"
                elif "drug" in name or "chem" in name or "pharma" in name: cat = "Drug Discovery"
                elif "clinical" in name or "medical" in name or "health" in name: cat = "Clinical/Medical"
                elif "cancer" in name or "tumor" in name or "oncology" in name: cat = "Oncology"
                elif "protein" in name or "antibody" in name: cat = "Protein/Structure"
                elif "agent" in name: cat = "AI Agents"
                elif "data" in name or "stats" in name or "viz" in name: cat = "Data/Visualization"
                else: cat = "Other"
                openclaw_categories[cat] = openclaw_categories.get(cat, 0) + 1
    packs.append({
        "id": "openclaw-medical",
        "name": "OpenClaw Medical Skills",
        "description": "869 skills médicas/científicas — Genômica, Bioinformática, Drug Discovery, IA Clínica",
        "total_skills": openclaw_count,
        "categories": openclaw_categories,
        "source": "FreedomIntelligence/OpenClaw-Medical-Skills",
        "installed": True,
        "path": str(OPENCLAW_SKILLS_DIR),
    })
    # NanoClaw
    nanoclaw_skills = []
    nanoclaw_path = NANOCLAW_DIR / ".claude" / "skills"
    if not nanoclaw_path.exists():
        nanoclaw_path = NANOCLAW_DIR
    packs.append({
        "id": "nanoclaw",
        "name": "NanoClaw",
        "description": "Assistente IA pessoal multi-canal — WhatsApp, Telegram, Discord, Slack, Gmail",
        "total_skills": 22,
        "categories": {
            "Channels": 8, "Setup": 3, "Integrations": 5,
            "Voice/Media": 3, "Management": 3,
        },
        "source": "qwibitai/nanoclaw",
        "installed": True,
        "path": str(NANOCLAW_DIR),
        "features": [
            "WhatsApp integration", "Telegram bot", "Discord bot",
            "Slack channel", "Gmail integration", "Voice transcription (Whisper)",
            "Agent Swarms", "Docker sandboxes", "Scheduled tasks",
            "X/Twitter posting", "PDF reading", "Image vision",
        ]
    })
    return {"packs": packs}

@app.get("/api/skill-packs/{pack_id}/skills")
def list_pack_skills(pack_id: str, category: str = None, search: str = None):
    skills = []
    if pack_id == "openclaw-medical" and OPENCLAW_SKILLS_DIR.exists():
        for skill_dir in sorted(OPENCLAW_SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir(): continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists(): continue
            name = skill_dir.name
            # Quick category
            if name.startswith("bio-"): cat = "Bioinformatics"
            elif name.startswith("tooluniverse-"): cat = "ToolUniverse"
            elif name.startswith("single-"): cat = "Single-Cell"
            elif name.startswith("bulk-"): cat = "Bulk Analysis"
            elif "drug" in name or "chem" in name or "pharma" in name: cat = "Drug Discovery"
            elif "clinical" in name or "medical" in name or "health" in name: cat = "Clinical/Medical"
            elif "cancer" in name or "tumor" in name or "oncology" in name: cat = "Oncology"
            elif "protein" in name or "antibody" in name: cat = "Protein/Structure"
            elif "agent" in name: cat = "AI Agents"
            elif "data" in name or "stats" in name or "viz" in name: cat = "Data/Visualization"
            else: cat = "Other"
            if category and cat != category: continue
            if search and search.lower() not in name.lower(): continue
            # Parse frontmatter for description
            try:
                content = skill_file.read_text(encoding="utf-8", errors="ignore")[:500]
                fm = parse_fm(content)
                desc = fm.get("description", name.replace("-", " ").replace("bio ", "").title())
            except:
                desc = name.replace("-", " ").title()
            skills.append({"id": name, "name": name, "category": cat, "description": desc})
    return {"skills": skills, "total": len(skills)}

@app.get("/")
def root():
    return FileResponse(str(BASE_DIR / "frontend" / "index.html"))

app.mount("/", StaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Agent Hub -> http://localhost:7080")
    uvicorn.run(app, host="0.0.0.0", port=7080)
