"""Agent Hub — VPS version (Linux paths, embedded agent data)"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3, json, os, httpx
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "hub.db"

# On VPS we embed agent configs directly (no local SKILL.md files)
AGENTS_CONFIG = [
    {"id": "agente-estrategico-manha", "name": "Manhã", "description": "Agente estratégico matinal — planeja o dia, define metas",
     "icon": "🌅", "color": "#f59e0b", "x": 50, "y": 30, "schedule": "08:00 diário"},
    {"id": "agente-desenvolvimento", "name": "Desenvolvimento", "description": "Agente de desenvolvimento — executa tarefas de código",
     "icon": "🛠️", "color": "#3b82f6", "x": 350, "y": 30, "schedule": "09:30 diário"},
    {"id": "agente-estrategico-noite", "name": "Noturno", "description": "Agente estratégico noturno — revisa o dia, gera relatórios",
     "icon": "🌙", "color": "#8b5cf6", "x": 700, "y": 30, "schedule": "21:00 diário"},
    {"id": "inspecao-geral-sistemas", "name": "Inspeção Sistemas", "description": "Inspeção geral de todos os sistemas e serviços",
     "icon": "🔍", "color": "#10b981", "x": 50, "y": 220, "schedule": "08:01 diário"},
    {"id": "verificador-publicacoes", "name": "Verificador Publicações", "description": "Verifica publicações e conteúdo agendado",
     "icon": "📡", "color": "#06b6d4", "x": 350, "y": 220, "schedule": "08:30 diário"},
    {"id": "atualizacao-deploy-verificacao", "name": "Deploy & Verificação", "description": "Deploy e verificação de atualizações nos sistemas",
     "icon": "🚀", "color": "#ef4444", "x": 700, "y": 220, "schedule": "manual"},
    {"id": "manutencao-correcao-sistemas", "name": "Manutenção & Correção", "description": "Manutenção preventiva e correção de bugs",
     "icon": "🔧", "color": "#f97316", "x": 50, "y": 410, "schedule": "manual"},
]

VIRTUAL_NODES = [
    {"id": "_whatsapp", "name": "WhatsApp", "icon": "📱", "color": "#22c55e", "x": 1000, "y": 30, "virtual": True},
    {"id": "_vps", "name": "VPS Reports", "icon": "💾", "color": "#ef4444", "x": 1000, "y": 220, "virtual": True},
    {"id": "_route_agent", "name": "Route Agent", "icon": "🗺️", "color": "#0ea5e9", "x": 1000, "y": 410, "virtual": True,
     "description": "Agente IA de Rotas: OR-Tools + ORS + HERE Traffic"},
    {"id": "_nanoclaw", "name": "NanoClaw", "icon": "🐾", "color": "#ec4899", "x": 350, "y": 410, "virtual": False,
     "description": "Assistente IA Multi-Canal: WhatsApp (Baileys), Telegram, Discord, Slack, Gmail",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "sempre ativo",
     "channels": ["WhatsApp", "Telegram", "Discord", "Slack", "Gmail", "X/Twitter"],
     "features": ["Voice Transcription", "Image Vision", "PDF Reader", "Agent Swarms", "Docker Sandboxes"]},
    {"id": "_email_agent", "name": "Email TRF1", "icon": "📧", "color": "#f59e0b", "x": 700, "y": 410, "virtual": False,
     "description": "Automação PJe + Outlook: upload PDFs, extrai dados, cria rascunhos, escritório virtual IA",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "sob demanda"},
]

CONNECTIONS = [
    {"from": "agente-estrategico-manha", "to": "agente-desenvolvimento", "label": "plano.json"},
    {"from": "agente-estrategico-manha", "to": "agente-estrategico-noite", "label": "metas"},
    {"from": "agente-desenvolvimento", "to": "agente-estrategico-noite", "label": "dev-report.json"},
    {"from": "agente-desenvolvimento", "to": "_whatsapp", "label": "resumo dev"},
    {"from": "agente-estrategico-noite", "to": "_whatsapp", "label": "resumo noturno"},
    {"from": "agente-estrategico-noite", "to": "_vps", "label": "noite.json"},
    {"from": "agente-desenvolvimento", "to": "_route_agent", "label": "rotas"},
    {"from": "_nanoclaw", "to": "_whatsapp", "label": "Baileys WS"},
    {"from": "agente-desenvolvimento", "to": "_nanoclaw", "label": "multi-canal"},
    {"from": "_nanoclaw", "to": "_email_agent", "label": "emails"},
    {"from": "agente-estrategico-manha", "to": "_email_agent", "label": "PJe diario"},
    # Extra project connections
    {"from": "_email_agent", "to": "_advocacia_demo", "label": "templates"},
    {"from": "_email_agent", "to": "_meuadvogado", "label": "LegalTech"},
    {"from": "agente-desenvolvimento", "to": "_cfo", "label": "financas"},
    {"from": "agente-desenvolvimento", "to": "_erp_analytics", "label": "analytics"},
    {"from": "_500_agents", "to": "agente-desenvolvimento", "label": "referencia"},
    {"from": "_cfo", "to": "_cloud_roi", "label": "ROI"},
    {"from": "_erp_analytics", "to": "_multicab_bi", "label": "BI data"},
    {"from": "_tester_agent", "to": "agente-desenvolvimento", "label": "bug reports"},
    {"from": "inspecao-geral-sistemas", "to": "_tester_agent", "label": "trigger tests"},
]

EXTRA_PROJECTS = [
    {"id": "_advocacia_demo", "name": "Advocacia Demo", "icon": "⚖️", "color": "#a855f7",
     "x": 50, "y": 630, "virtual": False, "category": "juridico",
     "description": "Site portfolio escritorio advocacia — HTML5, CSS3, jQuery, Particles.js",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "estatico",
     "stack": "HTML5 + CSS3 + jQuery"},
    {"id": "_meuadvogado", "name": "MeuAdvogadoOnline", "icon": "👨‍⚖️", "color": "#6366f1",
     "x": 300, "y": 630, "virtual": False, "category": "juridico",
     "description": "SaaS LegalTech — Next.js 15 + React 19 + TypeScript + Tailwind + Framer Motion",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "SaaS",
     "stack": "Next.js 15 + React 19 + TS"},
    {"id": "_cfo", "name": "CFO Automatizado", "icon": "💰", "color": "#10b981",
     "x": 550, "y": 630, "virtual": False, "category": "financas",
     "description": "CFO automatizado — Node.js + Express + Vue 3 + NeDB + Keycloak",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "full-stack",
     "stack": "Node.js + Vue 3 + TS"},
    {"id": "_cloud_roi", "name": "Cloud ROI Simulator", "icon": "☁️", "color": "#0ea5e9",
     "x": 800, "y": 630, "virtual": False, "category": "financas",
     "description": "Simulador ROI Cloud — framework decisao para negociacao AWS ($5.4M)",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "simulacao",
     "stack": "Python"},
    {"id": "_erp_analytics", "name": "ERP Analytics", "icon": "📊", "color": "#f43f5e",
     "x": 1050, "y": 630, "virtual": False, "category": "financas",
     "description": "Dashboard financeiro ERP — FastAPI + Streamlit + PostgreSQL + Plotly + ML",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "plataforma",
     "stack": "FastAPI + Streamlit + PG"},
    {"id": "_500_agents", "name": "500 AI Agents", "icon": "🤖", "color": "#8b5cf6",
     "x": 50, "y": 820, "virtual": False, "category": "ai",
     "description": "Colecao 500+ projetos IA — CrewAI, AutoGen, Agno, LangGraph por industria",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "referencia",
     "stack": "Python + JS frameworks"},
    {"id": "_multicab_bi", "name": "MultiCab BI", "icon": "📈", "color": "#14b8a6",
     "x": 300, "y": 820, "virtual": False, "category": "analytics",
     "description": "Framework BI governance — snapshots T+3/T+7 para marketplaces multi-plataforma",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "framework",
     "stack": "Metodologia + Docs"},
    {"id": "_tester_agent", "name": "Agente Tester", "icon": "🧪", "color": "#f43f5e",
     "x": 550, "y": 820, "virtual": False, "category": "devops",
     "description": "Testa APIs, UI/botões, VPS, console errors — Playwright + httpx + paramiko",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "manual",
     "stack": "Python + Playwright"},
    {"id": "_springboot", "name": "SpringBoot Labs", "icon": "🍃", "color": "#6db33f",
     "x": 800, "y": 820, "virtual": False, "category": "dev",
     "description": "6 projetos Spring Boot — API REST, Escola, Locadora, RH, Newsletter, Hello World",
     "has_report": False, "last_run": None, "report_date": None, "schedule": "estudo",
     "stack": "Java + Spring Boot + Maven"},
]

REPORTS_DIR = BASE_DIR / "reports"

app = FastAPI(title="Agent Hub")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:7080",
        "http://127.0.0.1:7080",
        "https://95.111.241.168",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)
    db = get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL, role TEXT NOT NULL,
        content TEXT NOT NULL,
        ts TEXT DEFAULT (datetime('now','localtime')))""")
    db.commit()
    db.close()


@app.on_event("startup")
def startup():
    init_db()


def read_report(aid):
    p = REPORTS_DIR / f"{aid}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except:
            pass
    return None


@app.get("/api/agents")
def list_agents():
    agents = []
    for cfg in AGENTS_CONFIG:
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
    agents.extend(VIRTUAL_NODES)
    agents.extend(EXTRA_PROJECTS)
    return {"agents": agents, "connections": CONNECTIONS}


@app.get("/api/agents/{aid}/report")
def get_report(aid: str):
    r = read_report(aid)
    return r if r else {"error": "Relatório não encontrado"}


@app.get("/api/agents/{aid}/skill")
def get_skill(aid: str):
    for cfg in AGENTS_CONFIG:
        if cfg["id"] == aid:
            return {"content": f"# {cfg['name']}\n\n{cfg['description']}\n\nSchedule: {cfg.get('schedule', 'N/A')}"}
    return {"content": ""}


class ChatMsg(BaseModel):
    agent_id: str
    message: str


@app.post("/api/chat")
def chat(body: ChatMsg):
    db = get_db()
    db.execute("INSERT INTO messages(agent_id,role,content) VALUES(?,?,?)",
               (body.agent_id, "user", body.message))
    db.commit()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if api_key:
        try:
            import anthropic as ant
            # Find agent config
            agent_cfg = next((c for c in AGENTS_CONFIG if c["id"] == body.agent_id), None)
            agent_name = agent_cfg["name"] if agent_cfg else body.agent_id
            agent_desc = agent_cfg["description"] if agent_cfg else ""
            report = read_report(body.agent_id)
            system = (f"Você é o agente '{agent_name}', um agente autônomo de IA pessoal. "
                      f"Responda de forma concisa em português BR.\n\n{agent_desc}")
            if report:
                system += f"\n\nSeu último relatório:\n{json.dumps(report, ensure_ascii=False)[:1500]}"
            hist = db.execute(
                "SELECT role,content FROM messages WHERE agent_id=? ORDER BY id DESC LIMIT 20",
                (body.agent_id,)).fetchall()
            messages = [{"role": r["role"], "content": r["content"]} for r in reversed(hist)]
            client = ant.Anthropic(api_key=api_key)
            resp = client.messages.create(model="claude-3-5-haiku-20241022", max_tokens=1024,
                                          system=system, messages=messages)
            reply = resp.content[0].text
        except Exception as e:
            reply = f"❌ Erro API: {e}"
    else:
        reply = ("⚙️ Configure `ANTHROPIC_API_KEY` no `.env` para ativar o chat.\n\n"
                 "Posso mostrar seus relatórios e configurações mesmo sem a chave!")
    db.execute("INSERT INTO messages(agent_id,role,content) VALUES(?,?,?)",
               (body.agent_id, "assistant", reply))
    db.commit()
    db.close()
    return {"reply": reply}


@app.get("/api/chat/{aid}/history")
def history(aid: str):
    db = get_db()
    rows = db.execute("SELECT role,content,ts FROM messages WHERE agent_id=? ORDER BY id",
                      (aid,)).fetchall()
    db.close()
    return [dict(r) for r in rows]


@app.delete("/api/chat/{aid}/history")
def clear_history(aid: str):
    db = get_db()
    db.execute("DELETE FROM messages WHERE agent_id=?", (aid,))
    db.commit()
    db.close()
    return {"ok": True}


@app.get("/api/skill-packs")
def list_skill_packs():
    return {"packs": [
        {
            "id": "openclaw-medical",
            "name": "OpenClaw Medical Skills",
            "description": "869 skills médicas/científicas — Genômica, Bioinformática, Drug Discovery, IA Clínica",
            "total_skills": 869,
            "categories": {"Bioinformatics": 380, "ToolUniverse": 120, "Single-Cell": 45,
                           "Drug Discovery": 80, "Clinical/Medical": 60, "Oncology": 40,
                           "Protein/Structure": 35, "AI Agents": 25, "Other": 84},
            "source": "FreedomIntelligence/OpenClaw-Medical-Skills",
            "installed": True,
        },
        {
            "id": "nanoclaw",
            "name": "NanoClaw",
            "description": "Assistente IA pessoal multi-canal — WhatsApp, Telegram, Discord, Slack, Gmail",
            "total_skills": 22,
            "categories": {"Channels": 8, "Setup": 3, "Integrations": 5, "Voice/Media": 3, "Management": 3},
            "source": "qwibitai/nanoclaw",
            "installed": True,
            "features": ["WhatsApp integration", "Telegram bot", "Discord bot",
                         "Slack channel", "Gmail integration", "Voice transcription (Whisper)",
                         "Agent Swarms", "Docker sandboxes", "Scheduled tasks",
                         "X/Twitter posting", "PDF reading", "Image vision"],
        }
    ]}


# Upload report endpoint (so local machine can push reports to VPS)
REPORT_TOKEN = os.getenv("REPORT_UPLOAD_TOKEN", "")

@app.post("/api/agents/{aid}/report")
async def upload_report(aid: str, data: dict, request: Request):
    token = request.headers.get("x-report-token", "")
    if not REPORT_TOKEN or token != REPORT_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing report token")
    # Sanitize aid to prevent path traversal
    safe_aid = "".join(c for c in aid if c.isalnum() or c in "-_")
    if not safe_aid or safe_aid != aid:
        raise HTTPException(status_code=400, detail="Invalid agent ID")
    p = REPORTS_DIR / f"{safe_aid}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@app.get("/")
def root():
    return FileResponse(str(BASE_DIR / "frontend" / "index.html"))


app.mount("/", StaticFiles(directory=str(BASE_DIR / "frontend"), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    print("Agent Hub VPS -> http://0.0.0.0:7080")
    uvicorn.run(app, host="0.0.0.0", port=7080)
