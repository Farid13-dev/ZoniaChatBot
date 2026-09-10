# 📁 qa_docs/views/model_llm.py
import os, glob, shutil, traceback, gc, torch, hashlib
from pathlib import Path
from typing import Optional
import asyncio
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from omegaconf import OmegaConf
from hashlib import md5
from qa_docs import get_db, context, UPLOAD_FOLDER
from qa_docs.db_relational import lite_relational
from rag.reader.directory_reader import DirectoryReader
from rag.pipeline.milvus_bm25_retriever import HybridSearchRetrieverPipeline
from rag.pipeline.contextual_generator_qa import ContextualQuestionGeneratorPipeline
from rag.config.schema import LlmConfig
from qa_docs.config.merge_config import merge_selected
from qa_docs.config.config import load_config, save_config
import logging
logger = logging.getLogger(__name__)

router_llm = APIRouter()

# ---------------------------------------------------------------------------
#  Config local
# ---------------------------------------------------------------------------
CORPUS_DIR = Path("uploads")
CORPUS_DIR.mkdir(exist_ok=True, parents=True)

# ---------------------------------------------------------------------------
#  SINGLETONS & CACHE (en memoria de proceso)
# ---------------------------------------------------------------------------
_pipeline: Optional[HybridSearchRetrieverPipeline] = None
_qgen: Optional[ContextualQuestionGeneratorPipeline] = None
_cfg_hash: Optional[str] = None


def _md5(path: str) -> str:
  with open(path, "rb") as f:
    return hashlib.md5(f.read()).hexdigest()


def _file_md5(path: str) -> str:
  with open(path, "rb") as f:
    return hashlib.md5(f.read()).hexdigest()


# ---------------------------------------------------------------------------
#  Runtime pipeline (Milvus + LLM + embeddings)
# ---------------------------------------------------------------------------

async def get_pipeline(request: Request) -> HybridSearchRetrieverPipeline:
  cfg_path = "configuration/config_process.yaml"
  cfg_hash = _file_md5(cfg_path)

  # ✅ Si ya existe en app.state y no cambió el YAML, reutiliza
  if (
    hasattr(request.app.state, "runtime_pipeline") and
    getattr(request.app.state, "pipeline_cfg_hash", None) == cfg_hash
  ):
    return request.app.state.runtime_pipeline

  # ♻️ Recarga completa
  logger.info("♻️ (Re)cargando Runtime pipeline...")

  import gc, torch
  gc.collect()
  if torch.cuda.is_available():
    torch.cuda.empty_cache()

  db_mgr = request.app.state.db_manager
  pipeline = await asyncio.to_thread(db_mgr.get_runtime_pipeline)

  # ✅ Guardar en app.state
  request.app.state.runtime_pipeline = pipeline
  request.app.state.pipeline_cfg_hash = cfg_hash
  return pipeline


# ---------------------------------------------------------------------------
#  Q-Gen pipeline  (no usa Milvus)
# ---------------------------------------------------------------------------
async def get_qgen(request: Request) -> ContextualQuestionGeneratorPipeline:
  cfg_path = "configuration/config_process.yaml"
  cfg_hash = _file_md5(cfg_path)

  if (
    hasattr(request.app.state, "qgen_pipeline") and
    getattr(request.app.state, "pipeline_cfg_hash", None) == cfg_hash
  ):
    return request.app.state.qgen_pipeline

  db_mgr = request.app.state.db_manager
  # Comparte el modelo de embeddings ya cargado por el pipeline principal
  # en vez de instanciar una segunda copia (~1.1 GB de VRAM de mas).
  runtime = getattr(request.app.state, "runtime_pipeline", None)
  shared_embed = getattr(runtime, "embed_model", None) if runtime else None
  qgen = ContextualQuestionGeneratorPipeline(
    llm_config=db_mgr.manager.get_llm_config(),
    embed_config=db_mgr.manager.get_embed_config(),
    splitter_config=db_mgr.manager.get_splitter_config(),
    qgen_config=db_mgr.manager.get_question_gen_config(),
    embed_model=shared_embed,
  )

  request.app.state.qgen_pipeline = qgen
  request.app.state.pipeline_cfg_hash = cfg_hash
  return qgen


# ---------------------------------------------------------------------------
#  Reconstruir PDF guardado en SQLite
# ---------------------------------------------------------------------------
async def rebuild_pdf(doc_id: int, db: AsyncSession) -> Path:
  stmt = select(lite_relational.Document).where(lite_relational.Document.id == doc_id)
  res = await db.execute(stmt)
  row = res.scalar_one_or_none()
  if row is None:
    raise ValueError(f"Documento {doc_id} no existe en SQLite.")

  # 🔄 Limpia otros PDFs (opcional si sólo quieres uno a la vez)
  for f in CORPUS_DIR.glob("*.pdf"):
    f.unlink()

  # ✔️ Guardar como archivo único
  out_path = CORPUS_DIR / row.name
  out_path.write_bytes(row.file_data)
  return out_path


# ---------------------------------------------------------------------------
#  Indexar en Milvus sólo si es necesario
# ---------------------------------------------------------------------------
async def ensure_indexed(doc_id: str,
                         pipeline: HybridSearchRetrieverPipeline) -> bool:
  """Carga (un solo) Document por PDF y lo indexa si aún no existe."""
  if pipeline.is_document_indexed(doc_id):
    return False

  # 🔒 Localiza el/los PDF recién guardados en la carpeta
  pdf_paths = glob.glob(str(CORPUS_DIR / "*.pdf"))

  # 📑 Carga cada PDF como UN Document (páginas concatenadas)
  docs = DirectoryReader(
    input_files=pdf_paths,
    # True une las paginas en UN documento antes de trocear. Con False cada
    # pagina era un Document aparte y el splitter no podia unir texto de dos
    # paginas: chunk_size quedaba sin efecto (50 paginas -> 52 nodos) y los
    # articulos partidos por un salto de pagina se cortaban a la mitad.
    concat_pages=True,
  ).load_data()

  # 🪄 Indexa en hilo aparte para no bloquear el event‑loop
  await asyncio.to_thread(
    pipeline.index_documents,
    docs,
    document_id=doc_id,
  )
  return True

# ---------------------------------------------------------------------------
#  Endpoint REST
# ---------------------------------------------------------------------------
@router_llm.post("/llm/process_document")
async def process_document(
  request: Request,
  db: AsyncSession = Depends(get_db),
):
  """
  1. Reconstruye el PDF guardado en SQLite.
  2. Carga (o reutiliza) el Runtime pipeline.
  3. Inserta el documento si no existe aún en Milvus.
  """
  try:
    # ID del documento que estamos procesando (proviene de tu YAML/ΩConf)
    db_mgr = request.app.state.db_manager
    #db_mgr.reload_config()
    doc_id = str(db_mgr.manager.get_processing_config().document_id)

    # 1) reconstruir archivo
    await rebuild_pdf(int(doc_id), db)

    # 2) runtime listo
    pipeline = await get_pipeline(request)

    # 3) indexar si procede
    inserted = await ensure_indexed(doc_id, pipeline)
    clear_sources_to_add()
    return JSONResponse(
      status_code=200,
      content={
        "status": "success",
        "message": (
          f"✅ Documento {doc_id} indexado."
          if inserted else
          f"❌ Documento {doc_id} ya estaba indexado."
        ),
      },
    )

  except Exception as exc:
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(exc))


async def preload_models(app):
  logger.info("⚙️ Preloading pipeline & QGen...")
  try:
    dummy_request = type("Request", (), {"app": app})()
    app.state.runtime_pipeline = await get_pipeline(dummy_request)
    app.state.qgen_pipeline = await get_qgen(dummy_request)
    logger.info("✅ Models preloaded.")
  except Exception as e:
    logger.info(f"❌ Error en preload: {e}")


@router_llm.post("/reload_models")
async def reload_models(request: Request):
  await preload_models(request.app)
  return {"message": "♻️ Modelos recargados correctamente."}


@router_llm.patch("/save_llm_config")
async def save_llm_config(request: LlmConfig):
  config = load_config()
  config.setdefault("llm", {})
  merge_selected(config, "llm", request)
  save_config(config)
  return {"message": "✅ Configuración de LLM guardada correctamente."}


@router_llm.get("/get_config")
async def get_config():
  config = load_config()
  config_dict = OmegaConf.to_container(config, resolve=True)
  return JSONResponse(content=config_dict)


@router_llm.get("/llm/available")
async def get_llm_available():
  config = load_config()
  llm_available = config.get("llm", {}).get("available", {})
  return JSONResponse(content=OmegaConf.to_container(llm_available, resolve=True))


@router_llm.get("/llm/selected")
async def get_llm_selected():
  llm_selected = load_config().get("llm", {}).get("selected", {})
  return JSONResponse(content=OmegaConf.to_container(llm_selected, resolve=True))


@router_llm.post("/clear_sources_to_add")
def clear_sources_to_add():
  context["sources_to_add"] = []
  try:
    shutil.rmtree(UPLOAD_FOLDER)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error al limpiar la carpeta: {str(e)}")

  return JSONResponse(
    content={"message": "Fuentes eliminadas correctamente", "sources_to_add": context["sources_to_add"]}
  )
