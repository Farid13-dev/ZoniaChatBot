from __future__ import annotations
import os
from pathlib import Path
from typing import List
import threading
from omegaconf import OmegaConf
from pymilvus import MilvusClient
import anyio

from rag.config.configuration import ConfigurationManager
from rag.pipeline.milvus_bm25_retriever import HybridSearchRetrieverPipeline
from rag.node.base_node import Document

from qa_docs import engine, r_db, CONTEXT_FILE, SOURCES_FILE


DEFAULT_CFG_PATH = "configuration/config_process.yaml"
INSTANCE_DB_PATH = Path("session/project.db")


class DatabaseManager:
  """Orquesta Milvus + SQLite y entrega un pipeline dinámico por instancia."""

  _runtime_lock = threading.Lock()

  def __init__(self, config_path: str = DEFAULT_CFG_PATH) -> None:
    self.config_path = config_path
    self.reload_config()
    uri = self.milvus_cfg.uri or f"http://{self.milvus_cfg.host}:{self.milvus_cfg.port}"
    self.milvus_client = MilvusClient(uri=uri)
    self.instance_db_path = INSTANCE_DB_PATH

  def reload_config(self):
    """Recarga el YAML desde disco y actualiza los managers."""
    self.config = OmegaConf.load(self.config_path)
    # Resuelve ${oc.env:VAR,default} in-place: ConfigurationManager hace
    # MilvusConfig(**db_config) y el desempaquetado NO resuelve interpolaciones,
    # asi que sin esto llegaria el literal "${oc.env:MILVUS_HOST,localhost}".
    OmegaConf.resolve(self.config)
    self.manager = ConfigurationManager(self.config)
    self.milvus_cfg = self.manager.get_db_config()

  # ---------- SQLite startup ------------------------------
  def init_sqlite_only(self) -> None:
    anyio.run(self._create_sqlite_tables)

  async def _create_sqlite_tables(self):
    async with engine.begin() as conn:
      await conn.run_sync(r_db.metadata.create_all)

  # ---------- Milvus + SQLite setup -----------------------
  def init_milvus_storage(self) -> None:
    """Valida colección Milvus y asegura SQLite."""
    pipe = self._build_pipeline()
    pipe.setup_storage()
    anyio.run(self._create_sqlite_tables)

  # ---------- Runtime (LLM, embeddings, retriever…) -------
  def get_runtime_pipeline(self) -> HybridSearchRetrieverPipeline:
    """Crea y configura un pipeline completo (embeddings + rerank)."""
    pipe = self._build_pipeline()
    with DatabaseManager._runtime_lock:
      if not pipe._components_ready.is_set():
        pipe.setup_runtime()
    return pipe

  def _build_pipeline(self) -> HybridSearchRetrieverPipeline:
    """Devuelve un pipeline limpio con la configuración actual."""
    return HybridSearchRetrieverPipeline(
      splitter_config=self.manager.get_splitter_config(),
      retriever_config=self.manager.get_index_retriever_config(),
      embed_config=self.manager.get_embed_config(),
      milvus_config=self.manager.get_db_config(),
      rerank_config=self.manager.get_rerank_config(),
      response_config=self.manager.get_response_config(),
      llm_config=self.manager.get_llm_config(),
    )

  # ---------- Indexación opcional --------------------------
  def index_documents(self, docs: List[Document], document_id: str) -> None:
    pipe = self.get_runtime_pipeline()
    pipe.index_documents(docs, document_id=document_id)

  # ---------- Utilidades de mantenimiento ------------------
  def delete_milvus_collection(self) -> None:
    name = self.milvus_cfg.collection_name
    if name in self.milvus_client.list_collections():
      self.milvus_client.drop_collection(name)
      print(f"✔️ Colección '{name}' eliminada.")
    else:
      print("ℹ️ Colección Milvus no encontrada.")

  def delete_sqlite_database(self) -> None:
    if self.instance_db_path.exists():
      self.instance_db_path.unlink()
      print("✔️ Base de datos SQLite eliminada.")
    else:
      print("ℹ️ Base de datos SQLite no encontrada.")

  def delete_files(self, *paths: str) -> None:
    for fp in paths:
      if os.path.exists(fp):
        os.remove(fp)
        print(f"✔️ Archivo eliminado: {fp}")

  def delete_context_files(self) -> None:
    for fp in [CONTEXT_FILE, SOURCES_FILE]:
      if os.path.exists(fp):
        os.remove(fp)
        print(f"✔️ Archivo eliminado: {fp}")

  async def close_sqlalchemy_engine(self) -> None:
    await engine.dispose()
    print("✔️ Conexión SQLAlchemy cerrada.")

  # ---------- Operaciones ligeras sobre Milvus -----------------
  def list_documents(self, limit: int = 1000):
      coll = self.milvus_cfg.collection_name
      # Tras /delete_databases la coleccion ya no existe, pero pymilvus
      # conserva cacheado su ID y consulta por el, fallando con
      # "collection not found[collection=468970410491982258]" -> 500 en la UI.
      # Con la coleccion ausente lo correcto es devolver lista vacia.
      try:
          if not self.milvus_client.has_collection(coll):
              return []
      except Exception:
          return []
      try:
          return self.milvus_client.query(
              collection_name=coll,
              filter='document_id != ""',
              limit=limit,
              output_fields=["document_id", "metadata"],
          )
      except Exception as exc:
          if "collection not found" in str(exc).lower() or "can't find collection" in str(exc).lower():
              return []
          raise

  def delete_document(self, document_id: str):
      coll = self.milvus_cfg.collection_name
      # Condición de borrado a partir de un campo string
      expr = f'document_id == "{document_id}"'
      self.milvus_client.delete(collection_name=coll, filter=expr)
