# 📁 configs_avanced.py

import os
import shutil

from fastapi import APIRouter, HTTPException, Depends,Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

from omegaconf import OmegaConf
from qa_docs import get_db, context
from qa_docs.db_relational import lite_relational
from qa_docs.config.merge_config import merge_selected
from qa_docs.config.config import load_config, save_config

from rag.config.schema import (
  NodeParserConfig,
  EmbeddingConfig,
  RerankConfig,
  RetrieverConfig
)
from qa_docs.runtime_reload import auto_reload
import logging
logger = logging.getLogger(__name__)

router_process = APIRouter()


@router_process.get("/list_sqlite_documents")
async def list_sqlite_documents(db: AsyncSession = Depends(get_db)):
  try:
    check_table_stmt = text("SELECT name FROM sqlite_master WHERE type='table' AND name='document'")
    result = await db.execute(check_table_stmt)
    if not result.scalar_one_or_none():
      return []

    result = await db.execute(select(lite_relational.Document))
    documents = result.scalars().all()
    return [{"id": doc.id, "name": doc.name, "categoria": doc.categoria} for doc in documents]
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error al consultar documentos: {str(e)}")


@router_process.post("/select_sqlite_document/{document_id}")
async def select_sqlite_document(document_id: int):
  config = load_config()
  config["processing"] = {"document_id": document_id}
  save_config(config)
  return JSONResponse(status_code=200, content={"message": f"✅ Documento {document_id} seleccionado."})


@router_process.patch("/save_retriever_config")
@auto_reload
async def save_retriever_config(body: RetrieverConfig, request: Request):
  config = load_config()
  config["retriever"] = body.__dict__
  save_config(config)
  return {"message": "✅ Configuración de Retriever guardada correctamente."}


@router_process.patch("/save_splitter_config")
@auto_reload
async def save_splitter_config(body: NodeParserConfig, request: Request):
  config = load_config()
  config.merge_with({"splitter": {"selected": body.__dict__}})
  save_config(config)
  return {"message": "✅ Configuración de Splitter guardada correctamente."}


@router_process.patch("/save_embedding_config")
@auto_reload
async def save_embedding_config(body: EmbeddingConfig, request: Request):
  config = load_config()
  merge_selected(config, "embedding", body)
  save_config(config)
  return {"message": "✅ Configuración de Embedding guardada correctamente."}


@router_process.patch("/save_reranking_config")
@auto_reload
async def save_reranking_config(body: RerankConfig, request: Request):
  config = load_config()
  merge_selected(config, "rerank", body)
  save_config(config)
  return {"message": "✅ Configuración de Reranking guardada correctamente."}


@router_process.get("/get_config")
async def get_config():
  config = load_config()
  config_dict = OmegaConf.to_container(config, resolve=True)
  return JSONResponse(content=config_dict)


@router_process.get("/splitter/available")
async def get_splitter_available():
  config = load_config()
  available = config.get("splitter", {}).get("available", {})
  return JSONResponse(content=OmegaConf.to_container(available, resolve=True))


@router_process.get("/embedding/available")
async def get_embedding_available():
  config = load_config()
  available = config.get("embedding", {}).get("available", {})
  return JSONResponse(content=OmegaConf.to_container(available, resolve=True))


@router_process.get("/rerank/available")
async def get_reranking_available():
  config = load_config()
  available = config.get("rerank", {}).get("available", {})
  return JSONResponse(content=OmegaConf.to_container(available, resolve=True))


@router_process.get("/splitter/selected")
async def get_splitter_selected():
  splitter_selected = load_config().get("splitter", {}).get("selected", {})
  return JSONResponse(content=OmegaConf.to_container(splitter_selected, resolve=True))


@router_process.get("/embedding/selected")
async def get_embedding_selected():
  embedding_selected = load_config().get("embedding", {}).get("selected", {})
  return JSONResponse(content=OmegaConf.to_container(embedding_selected, resolve=True))


@router_process.get("/rerank/selected")
async def get_reranking_selected():
  reranking_selected = load_config().get("rerank", {}).get("selected", {})
  return JSONResponse(content=OmegaConf.to_container(reranking_selected, resolve=True))
