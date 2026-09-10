# qa_docs/__init__.py
# Configuración principal de FastAPI + SQLite optimizada (modo WAL)

import os
import sys
import json

# La consola de Windows usa cp1252 y el proyecto imprime emojis (print y
# logging) por todas partes: sin esto, un simple "✅" tumba el arranque con
# UnicodeEncodeError. Reconfigurar la salida a UTF-8 lo resuelve de raiz.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from dotenv import load_dotenv

# Carga .env ANTES de que se lea la configuracion: el YAML referencia
# ${oc.env:GROQ_API_KEY} y OmegaConf lo resuelve desde el entorno.
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import event
from qa_docs.tts.TTSZ import TTSResponder
import logging
logger = logging.getLogger(__name__)

# ────────────────────────────
# 📁 Paths y carpetas
# ────────────────────────────
UPLOAD_FOLDER = "uploads"
DB_FOLDER = "session"
CONTEXT_FILE = "context.json"
SOURCES_FILE = "sources.txt"
ALLOWED_EXTENSIONS = {"pdf", "txt"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DB_FOLDER, exist_ok=True)

# ────────────────────────────
# 🚀 FastAPI
# ────────────────────────────
app = FastAPI()

# PDF.js y corpus embebido
app.mount("/pdfjs", StaticFiles(directory="static/pdfjs"), name="pdfjs")

PDF_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "../corpus_emb"))
if not os.path.exists(PDF_FOLDER):
    raise RuntimeError(f"❌ La carpeta de PDFs no existe: {PDF_FOLDER}")

app.mount("/corpus_emb", StaticFiles(directory=PDF_FOLDER), name="corpus_emb")

# CORS – admin y user UIs
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4203",
        "http://localhost:4202",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ────────────────────────────
# 🗃️ SQLite (modo async + WAL)
# ────────────────────────────
DATABASE_URL = f"sqlite+aiosqlite:///{DB_FOLDER}/project.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"timeout": 30},
)

@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(conn, _):
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA cache_size=-16000")
    cur.close()

SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
r_db = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session

# ────────────────────────────
# 📂 Contexto persistente
# ────────────────────────────
context = {
    "chat_items": [],
    "waiting": False,
    "time_intervals": {},
    "collection_exists": False,
    "sources_to_add": [],
    "sources": [],
    "processing_sources": False,
    "tts_active": True,
    "subq_active": True,
}

if os.path.exists(CONTEXT_FILE):
    with open(CONTEXT_FILE) as f:
        context.update(json.load(f))

if os.path.exists(SOURCES_FILE):
    with open(SOURCES_FILE) as f:
        context["sources"] = [l.strip() for l in f]
        context["collection_exists"] = True

def save_context() -> None:
    """Guarda contexto y fuentes en disco (llámalo desde endpoints si aplica)."""
    snapshot = context.copy()
    snapshot.update({"chat_items": [], "time_intervals": {}, "waiting": False})
    with open(CONTEXT_FILE, "w") as f:
        json.dump(snapshot, f, indent=4)
    with open(SOURCES_FILE, "w") as f:
        f.write("\n".join(context["sources"]))

# 🔴 Eliminado el sistema de backup periódico por tiempo

# ────────────────────────────
# 🌐 Routers
# ────────────────────────────
from qa_docs.views.sources import router_sources
from qa_docs.views.configs_avanced import router_process
from qa_docs.views.model_llm import router_llm
from qa_docs.views.chat_zonia import router_chat
from qa_docs.routers.feature_flags_router import router_feature_flags

app.include_router(router_sources)
app.include_router(router_process)
app.include_router(router_llm)
app.include_router(router_chat)
app.include_router(router_feature_flags)

# ────────────────────────────
# ⚡ Eventos de ciclo de vida
# ────────────────────────────
def _clear_gpu():
    import torch, gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()

@app.on_event("startup")
async def on_startup():
    from qa_docs.db_relational.db_manager import DatabaseManager
    from qa_docs.views.model_llm import preload_models

    app.state.db_manager = DatabaseManager()
    await preload_models(app)

    app.state.tts = TTSResponder("es-mx-laurav2")
    app.state.feature_flags = {
        "subq_active": context.get("subq_active", True),
        "tts_active": context.get("tts_active", True),
    }

    _clear_gpu()
    logger.info("🚀 FastAPI iniciado con SQLite (WAL) y Milvus on-demand")

@app.on_event("shutdown")
async def on_shutdown():
    dbm = app.state.db_manager
    await dbm.close_sqlalchemy_engine()
    logger.info("🛑 FastAPI apagada.")
