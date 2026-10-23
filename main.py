import os
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.services.scheduler import start_scheduler
from app.routes.repos import router as repos_router
from app.routes.posts import router as posts_router
from app.routes.settings import router as settings_router
from app.routes.actions import router as actions_router
from app.routes.webhooks import router as webhooks_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "app", "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "app", "templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    print("\n" + "="*60)
    print("[GitPost] Servidor iniciado com sucesso!")
    print("[GitPost] Painel Web disponivel em: http://localhost:8000")
    print("="*60 + "\n")
    yield

app = FastAPI(
    title="GitPost - GitHub to LinkedIn Automation",
    description="Sistema inteligente de monitoramento do GitHub com aprovação por email e postagem no LinkedIn",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Arquivos Estáticos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Rotas de API
app.include_router(repos_router)
app.include_router(posts_router)
app.include_router(settings_router)
app.include_router(actions_router)
app.include_router(webhooks_router)

# Rota principal Dashboard
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content=content)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
