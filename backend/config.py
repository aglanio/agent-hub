"""Configuracao centralizada — detecta ambiente local vs VPS automaticamente."""

import os
import platform
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Deteccao de ambiente ─────────────────────────────────────
IS_VPS = os.getenv("IS_VPS", "").lower() in ("true", "1", "yes") or platform.system() == "Linux"

# ── Paths ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent  # agent-hub/
BACKEND_DIR = Path(__file__).parent       # agent-hub/backend/
DATA_DIR = BACKEND_DIR / "data"
DB_PATH = BASE_DIR / "data" / "hub.db"
FRONTEND_DIR = BASE_DIR / "frontend"

if IS_VPS:
    REPORTS_DIR = BASE_DIR / "reports"
    TASKS_DIR = None
    OPENCLAW_SKILLS_DIR = None
    NANOCLAW_DIR = None
    ROUTE_AGENT_PATH = None
    PROJECTS_DIR = None
else:
    REPORTS_DIR = Path(r"C:\Users\aglan\.claude\agent-reports")
    TASKS_DIR = Path(r"C:\Users\aglan\.claude\scheduled-tasks")
    OPENCLAW_SKILLS_DIR = Path(r"C:\Users\aglan\.claude\skills")
    NANOCLAW_DIR = Path(r"C:\Users\aglan\OneDrive\Documentos\claude projetos\agentes de ia claude\nanoclaw\nanoclaw-main")
    ROUTE_AGENT_PATH = Path(r"C:\Users\aglan\OneDrive\Documentos\claude projetos\mapas\route-agent")
    PROJECTS_DIR = Path(r"C:\Users\aglan\OneDrive\Documentos\claude projetos\projetos-extras")

# ── API Keys & Tokens ───────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
REPORT_UPLOAD_TOKEN = os.getenv("REPORT_UPLOAD_TOKEN", "")
PORT = int(os.getenv("PORT", "7080"))

# ── CORS Origins ─────────────────────────────────────────────
CORS_ORIGINS = [
    "http://localhost:7080",
    "http://127.0.0.1:7080",
]
if IS_VPS:
    CORS_ORIGINS.append("https://95.111.241.168")
else:
    CORS_ORIGINS.append("https://saas.vendedorgpt.com.br")
