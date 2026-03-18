"""Agent Hub — App factory unificado (local + VPS)."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.config import CORS_ORIGINS, FRONTEND_DIR, PORT, IS_VPS
from backend.database import init_db
from backend.routers import agents, chat, skills, health


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Hub")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Startup
    @app.on_event("startup")
    def startup():
        init_db()

    # Routers
    app.include_router(agents.router)
    app.include_router(chat.router)
    app.include_router(skills.router)
    app.include_router(health.router)

    # Frontend
    @app.get("/")
    def root():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="static")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    env = "VPS" if IS_VPS else "Local"
    print(f"Agent Hub ({env}) -> http://0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
