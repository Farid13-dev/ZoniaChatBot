# milvus_bm25_retriever.py
# ---------------------------------------------------------------------------
# Hybrid Search Retriever Pipeline – versión 2025-05-17 (optimizada)
# ---------------------------------------------------------------------------
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import Dict, Iterable, Optional, Tuple, Sequence
import copy

# —— RAG internals ----------------------------------------------------------
from rag.callbacks import CallbackManager
from rag.config.schema import (
  EmbeddingConfig,
  LlmConfig,
  MilvusConfig,
  NodeParserConfig,
  RerankConfig,
  ResponseConfig,
  RetrieverConfig,
)
from rag.core.prompt_helper import PromptHelper
from rag.core.service_context import ServiceContext
from rag.core.storage_context import StorageContext
from rag.embeddings.huggingface import HuggingFaceEmbedding
from rag.embeddings.openai import OpenAIEmbedding
from rag.embeddings.sbert import SBertEmbedding
from rag.engine.retriever_engine import RetrieverQueryEngine
from rag.indices.vector_store import VectorStoreIndex
from rag.node.base_node import Document
from rag.node_parser.text.sentence import SentenceSplitter  # anotación
from rag.retrievers.dense.vector_retriver import VectorIndexRetriever
from rag.retrievers.hybrid_retriever import HybridSearchRetriever
from rag.retrievers.sparse.bm25 import BM25Retriever
from rag.retrievers.types import QueryBundle, QueryType  # anotación
from rag.rerank.sbert_rerank import SentenceTransformerRerank
from rag.rerank.transformer import TransformerRerank
from rag.synthesizer.utils import get_response_synthesizer
from rag.vector_stores.milvus import MilvusVectorStore
from rag.prompt.selector_template import DEFAULT_TEXT_QA_PROMPT_SEL

_ENGINE_CACHE_LIMIT = 32  # número máximo de engines en memoria
_cache_lock = threading.RLock()  # protege el LRU

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

@contextmanager
def _timed(section: str):
  """Log del tiempo de ejecución de un bloque."""
  start = perf_counter()
  try:
    yield
  finally:
    elapsed = (perf_counter() - start) * 1_000
    logger.debug("%s took %.1f ms", section, elapsed)


@dataclass(slots=True)
class _ComponentBundle:
  service_ctx: ServiceContext
  storage_ctx: StorageContext
  vector_store: MilvusVectorStore
  index: VectorStoreIndex
  dense_retriever: VectorIndexRetriever
  node_parser: SentenceSplitter
  node_reranker: "BaseReranker"


# ---------------------------------------------------------------------------
# Main class – indexing + hybrid retrieval
# ---------------------------------------------------------------------------

class HybridSearchRetrieverPipeline:
  """Hybrid dense+sparse search sobre Milvus con alta concurrencia."""

  _init_lock = threading.Lock()  # protege secciones críticas

  # —————————————————————————————— INIT ————————————————————————————
  def __init__(
    self,
    *,
    splitter_config: NodeParserConfig,
    retriever_config: RetrieverConfig,
    embed_config: EmbeddingConfig,
    milvus_config: MilvusConfig,
    rerank_config: RerankConfig,
    response_config: ResponseConfig,
    llm_config: LlmConfig,
  ) -> None:
    # Configs
    self.splitter_config = splitter_config
    self.retriever_config = retriever_config
    self.milvus_config = milvus_config
    self.rerank_config = rerank_config
    self.response_config = response_config
    self.llm_config = llm_config

    # Lazy singletons
    self._components: Optional[_ComponentBundle] = None
    self._components_ready = threading.Event()
    self._storage_ready = threading.Event()

    # Se inicializan después en setup_storage()
    self._vector_store: Optional[MilvusVectorStore] = None
    self._storage_ctx: Optional[StorageContext] = None

    # Runtime helpers
    self.callback_mgr = CallbackManager()
    self.embed_model = self._build_embedding_model(embed_config)

  # —————————————————————————— PUBLIC HELPERS —————————————————————————
  def is_document_indexed(self, document_id: str) -> bool:
    """Comprueba si un ID ya existe en Milvus (no lanza excepciones)."""
    try:
      self.setup_storage()
      return self._vector_store.exists_document_id(str(document_id))  # type: ignore
    except Exception:
      return False

  # ───────────────────────────────────────────────────────────────
  # 1) Storage (Milvus + StorageContext)
  # ───────────────────────────────────────────────────────────────
  def setup_storage(self) -> None:
    """Crea (o se conecta a) la colección Milvus. Idempotente."""
    if self._storage_ready.is_set():
      return

    with self._init_lock:
      if self._storage_ready.is_set():
        return

      self._vector_store = MilvusVectorStore(
        dim=self.embed_model.get_model_dim(),
        host=self.milvus_config.host,
        port=self.milvus_config.port,
        uri=self.milvus_config.uri,
        address=self.milvus_config.address,
        user=self.milvus_config.user,
        collection_name=self.milvus_config.collection_name,
        embedding_field=self.milvus_config.embedding_field,
        doc_id_field=self.milvus_config.primary_field,
        text_field=self.milvus_config.text_field,
        consistency_level=self.milvus_config.consistency_level,
        overwrite=False,  # clave
        index_params=self.milvus_config.index_params,
        search_params=self.milvus_config.search_params,
      )

      # Sólo StorageContext (sin índice ni modelos)
      self._storage_ctx = StorageContext.from_defaults(
        vector_store=self._vector_store
      )

      self._storage_ready.set()
      logger.info("✅ Milvus collection lista.")

  # ───────────────────────────────────────────────────────────────
  # 2) Runtime (embeddings, índice, LLM, reranker…)
  # ───────────────────────────────────────────────────────────────
  def setup_runtime(self) -> None:
    """Carga TODOS los componentes necesarios para indexar y consultar."""
    self.setup_storage()

    if self._components_ready.is_set():
      return

    with self._init_lock:
      if self._components_ready.is_set():
        return

      self._components = self._build_components()
      self._components_ready.set()
      logger.info("🎯 Runtime listo.")

  # Compatibilidad legacy
  def setup(self) -> None:
    self.setup_runtime()


  # ————————————————————————— ÍNDICE ———————————————————————————
  def index_documents(self, docs: Sequence[Document], *, document_id: str) -> bool:
    self._ensure_ready()
    comp = self._components
    assert comp is not None

    vs = comp.vector_store
    if vs.exists_document_id(document_id):
      logger.warning("⚠️ document_id=%s ya indexado – se omite", document_id)
      return True

    with _timed("parse & insert"):
      # El mapa de paginas se saca ANTES de trocear: node_parser copia la
      # metadata del documento a CADA nodo (base.py) y, con
      # include_metadata=True, esa metadata se antepone al texto del chunk
      # comiendose el presupuesto de tokens (se pasaba de 23 a 66 nodos).
      mapas = {}
      for d in docs:
        pm = (d.metadata or {}).pop("_page_map", None)
        if pm:
          mapas[d.id_] = (d.text, pm)

      nodes = comp.node_parser.get_nodes_from_documents(docs, show_progress=True)

      for n in nodes:
        n.metadata["document_id"] = document_id
        n.metadata.pop("_page_map", None)
        datos = mapas.get(getattr(n, "ref_doc_id", None))
        if datos is None and len(mapas) == 1:
          datos = next(iter(mapas.values()))
        if datos:
          texto_doc, page_map = datos
          # start_char_idx no siempre se rellena; si falta, se localiza el
          # trozo en el texto original.
          inicio = getattr(n, "start_char_idx", None)
          if inicio is None:
            inicio = texto_doc.find(n.text)
          if inicio is not None and inicio >= 0:
            pagina = page_map[0][1]
            for comienzo, num in page_map:
              if inicio >= comienzo:
                pagina = num
              else:
                break
            n.metadata["num_page"] = pagina
      comp.index.insert_nodes(nodes)
    return True

  # ————————————————————— Engine cache ——————————————————————
  def _engine_cache_init(self):
    if not hasattr(self, "_engine_cache"):
      self._engine_cache: "OrderedDict[tuple, RetrieverQueryEngine]" = OrderedDict()

  def _get_cached_engine(self, key, builder):
    with _cache_lock:
      cache = self._engine_cache
      if key in cache:
        cache.move_to_end(key)  # LRU
        return cache[key]
      if len(cache) >= _ENGINE_CACHE_LIMIT:
        cache.popitem(last=False)  # expulsa LRU
      eng = builder()
      cache[key] = eng
      return eng

  # ————————————————————————— CONSULTA —————————————————————————
  def query(
    self,
    query: QueryType,
    *,
    document_ids: Optional[Iterable[str]] = None,
    bm25_topk_override: Optional[int] = None,
  ):
    """
    • Cachea el RetrieverQueryEngine por combinación (docs, bm25_top_k).
    • Evita traer nodos BM25 al proceso: búsqueda sparse en Milvus.
    • Mantiene el reranker.
    """

    self._ensure_ready()
    comp = self._components  # garantizado no-None

    # Asegurar cache interno
    self._engine_cache_init()

    # 1⃣ Validar / reformular con LLM
    qry = self.validate_and_reformulate(comp, query)
    # print("query reformulada:", qry)
    if isinstance(qry, str):
      from rag.synthesizer.simple_stream import SimpleStreamResponse
      return SimpleStreamResponse(qry), []

    query_bundle = qry
    bm25_k = bm25_topk_override or self.retriever_config.sparse_top_k
    cache_key = (frozenset(document_ids) if document_ids else None, bm25_k)

    # ─── builder ejecutado la 1ª vez para esa combinación ───
    def _build_engine():
      # --- dense ------------------------------------------------------
      dense = comp.dense_retriever.clone(
        _doc_ids=[str(d) for d in document_ids] if document_ids else None
      )

      # --- sparse -----------------------------------------------------
      if document_ids:
        try:
          nodes_bm25 = comp.vector_store.get_nodes_by_document_ids(list(document_ids))
        except AttributeError:
          nodes_bm25 = []
          for did in document_ids:
            nodes_bm25.extend(
              comp.vector_store.get_nodes_by_document_id(str(did))
            )
      else:
        # Búsqueda sparse directa (no traer toda la colección)
        nodes_bm25 = comp.vector_store.search_sparse(query_bundle, top_k=bm25_k)

      sparse = BM25Retriever(
        nodes=nodes_bm25,
        similarity_top_k=bm25_k,
        callback_manager=comp.service_ctx.callback_manager,
      )

      # --- hybrid + engine -------------------------------------------
      hybrid = HybridSearchRetriever(
        sparse_retriever=sparse,
        dense_retriever=dense,
        mode=self.retriever_config.hybrid_mode,
        callback_manager=comp.service_ctx.callback_manager,
      )

      return RetrieverQueryEngine(
        retriever=hybrid,
        response_synthesizer=comp.service_ctx.response_synthesizer,
        node_postprocessors=[comp.node_reranker],
      )

    engine = self._get_cached_engine(cache_key, _build_engine)

    # 3⃣ Retrieve → Rerank → Synthesize
    with _timed("retrieve & synthesize"):
      nodes = engine.retrieve(query_bundle)
      response = comp.service_ctx.response_synthesizer.synthesize(query_bundle, nodes)

    return response, nodes

  def query_one(self, query: QueryType, *, document_id: str):
    return self.query(query, document_ids=[document_id])

  # ——————————————————— Reformulación / intención ———————————————————
  def validate_and_reformulate(self, comp, query_str: str) -> QueryBundle | str:
    from rag.constants.default_prompt import REFORMULATE_WITH_INTERNAL_KEYWORDS

    etiqueta, mensaje = self.detectar_intencion(comp, query_str)

    if etiqueta != "positivo":
      return mensaje  # se detiene aquí

    try:
      prompt_text = REFORMULATE_WITH_INTERNAL_KEYWORDS.format(question=query_str)
      query_reformulada = comp.service_ctx.llm.predict(prompt_text).strip()
      return QueryBundle(query_str=query_reformulada)
    except Exception:
      return "⚠️ Ocurrió un error al procesar tu pregunta. Intenta de nuevo."

  def detectar_intencion(self, comp, query: str) -> tuple[str, str]:
    from rag.constants.default_prompt import PROMT_USER_INTENT_TREE
    import re, json

    try:
      result = comp.service_ctx.llm.predict(
        prompt=PROMT_USER_INTENT_TREE,
        query_str=query,
      )
      cleaned = re.sub(r"```(?:json)?|```", "", result).strip()
      parsed = json.loads(cleaned)
      etiqueta = parsed.get("etiqueta", "").lower()
      motivo = parsed.get("motivo", "").lower()
      mensaje = self.handle_intent(etiqueta, motivo)
      return etiqueta, mensaje
    except Exception:
      return "negativo", "⚠️ No puedo responder en este momento. Intenta más tarde."

  def handle_intent(self, etiqueta: str, motivo: str) -> str:
    if etiqueta == "neutro":
      if "saludo" in motivo:
        return "👋 ¡Hola! ¿En qué puedo ayudarte hoy?"
      if "despedida" in motivo:
        return "👋 ¡Hasta luego!"
      if "agradecimiento" in motivo:
        return "😊 ¡Con gusto!"
      return "🙂 Gracias por tu mensaje."
    if etiqueta == "negativo":
      return "⚠️ No puedo responder a eso. Por favor, intenta con algo relacionado al estatuto."
    return ""

  # ————————————————————————— PRIVATE ——————————————————————————
  def _ensure_ready(self):
    if not self._components_ready.is_set():
      raise RuntimeError("Pipeline no inicializado – llama a setup() primero")

  def _build_components(self) -> _ComponentBundle:
    """Construye singleton components reutilizando storage existente."""
    logger.info("Construyendo singleton components…")

    # 1) VectorStore
    if self._vector_store is None:  # fallback si skippearon setup_storage()
      self._vector_store = MilvusVectorStore(
        dim=self.embed_model.get_model_dim(),
        host=self.milvus_config.host,
        port=self.milvus_config.port,
        uri=self.milvus_config.uri,
        address=self.milvus_config.address,
        user=self.milvus_config.user,
        collection_name=self.milvus_config.collection_name,
        embedding_field=self.milvus_config.embedding_field,
        doc_id_field=self.milvus_config.primary_field,
        text_field=self.milvus_config.text_field,
        consistency_level=self.milvus_config.consistency_level,
        overwrite=False,
        index_params=self.milvus_config.index_params,
        search_params=self.milvus_config.search_params,
      )

    vector_store = self._vector_store

    # 2) Node parser
    node_parser = self._init_splitter()

    tokenizer = self._tokenizer_model().encode

    # 3) Prompt helper
    # Estaba fijo en 8192/512 e ignoraba la configuracion del LLM: subir
    # context_window desde la UI no tenia ningun efecto. max_input_size sale
    # de context_window - num_output, asi que num_output alto recorta el
    # contexto que llega al modelo.
    prompt_helper = PromptHelper(
      tokenizer=tokenizer,
      context_window=int(getattr(self.llm_config, "context_window", 8192) or 8192),
      num_output=int(getattr(self.llm_config, "max_tokens", 512) or 512),
    )

    # 4) ServiceContext
    service_ctx = ServiceContext(
      llm=self.llm_config,
      prompt_helper=prompt_helper,
      embed_model=self.embed_model,
      node_parser=node_parser,
      callback_manager=self.callback_mgr,
    )
    service_ctx.response_synthesizer = get_response_synthesizer(
      service_context=service_ctx,
      callback_manager=service_ctx.callback_manager,
      response_mode=self.response_config.response_mode,
      text_qa_template=DEFAULT_TEXT_QA_PROMPT_SEL,
      verbose=self.response_config.verbose,
      use_async=self.response_config.use_async,
      streaming=self.response_config.streaming,
    )

    # 5) StorageContext
    if self._storage_ctx is None:
      self._storage_ctx = StorageContext.from_defaults(vector_store=vector_store)
    storage_ctx = self._storage_ctx

    # 6) Index
    index = VectorStoreIndex.from_vector_store(
      vector_store=vector_store,
      storage_context=storage_ctx,
      service_context=service_ctx,
    )

    dense_retriever = VectorIndexRetriever(
      index=index,
      similarity_top_k=self.retriever_config.similarity_top_k,
      sparse_top_k=self.retriever_config.sparse_top_k,
      alpha=self.retriever_config.alpha,
      vector_store_query_mode=self.retriever_config.vector_store_query_mode,
    )
    node_reranker = self._build_reranker()

    return _ComponentBundle(
      service_ctx=service_ctx,
      storage_ctx=storage_ctx,
      vector_store=vector_store,
      index=index,
      dense_retriever=dense_retriever,
      node_parser=node_parser,
      node_reranker=node_reranker,
    )

  # ——— Fábricas auxiliares (splitter, reranker, embeddings) ————————
  def _init_splitter(self):
    cfg = self.splitter_config

    tokenizer = self._tokenizer_model()
    mode = cfg.splitter_mode.lower()

    if mode == "sentence":
      from rag.node_parser.text.sentence import SentenceSplitter
      return SentenceSplitter(
        separator=cfg.separator,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        tokenizer=tokenizer.encode,
        paragraph_separator=cfg.paragraph_separator,
        secondary_chunking_regex=cfg.secondary_chunking_regex,
        callback_manager=self.callback_mgr,
      )
    if mode == "token":
      from rag.node_parser.text.token import TokenTextSplitter
      return TokenTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        separator=cfg.separator,
        backup_separators=cfg.backup_separators,
        include_metadata=cfg.include_metadata,
        include_prev_next_rel=cfg.include_prev_next_rel,
        tokenizer=tokenizer.encode,
      )
    if mode == "sentence_window":
      from rag.node_parser.text.sentence_window import SentenceWindowNodeParser
      return SentenceWindowNodeParser.from_defaults(
        sentence_splitter=None,
        window_size=cfg.window_size,
        include_metadata=cfg.include_metadata,
        include_prev_next_rel=cfg.include_prev_next_rel,
      )
    if mode == "legal_structure":
      from rag.node_parser.relationship.legal_structure import LegalStructureParser
      return LegalStructureParser(tokenizer=tokenizer)

    raise ValueError(f"Splitter mode '{cfg.splitter_mode}' no soportado.")

  def _build_reranker(self):
    cfg = self.rerank_config
    provider = cfg.provider.lower()
    if provider == "huggingface":
      return TransformerRerank(
        model_name_or_path=cfg.model_name,
        tokenizer_name=cfg.tokenizer_name,
        token=cfg.token,
        top_n=cfg.top_n,
        max_length=cfg.max_length,
        trust_remote_code=cfg.trust_remote_code,
        device=cfg.device,
      )
    if provider == "sentence-transformers":
      return SentenceTransformerRerank(
        model_name=cfg.model_name,
        top_n=cfg.top_n,
        max_length=cfg.max_length,
        trust_remote_code=cfg.trust_remote_code,
        device=cfg.device,
      )
    raise ValueError(f"Reranker provider '{provider}' no soportado.")

  def _tokenizer_model(self):
    cfg = self.splitter_config
    name = cfg.model_name_tokenizer
    if name.lower() == "cl100k_base":
      import tiktoken
      return tiktoken.get_encoding("cl100k_base")
    if "bge-m3" in name.lower():
      from transformers import AutoTokenizer
      return AutoTokenizer.from_pretrained(name)
    raise ValueError(f"Tokenizer '{name}' no soportado.")

  @staticmethod
  def _build_embedding_model(cfg: EmbeddingConfig):
    provider = getattr(cfg, "provider", "huggingface").lower()
    if provider == "openai":
      return OpenAIEmbedding(
        model_name=cfg.model_name,
        api_key=cfg.api_key,
        normalize=cfg.normalize,
        embedding_batch_size=cfg.embedding_batch_size,
      )
    if provider == "huggingface":
      return HuggingFaceEmbedding(
        model_name=cfg.model_name,
        tokenizer_name=cfg.tokenizer_name,
        pooling=cfg.pooling,
        max_length=cfg.max_length,
        stride=cfg.stride,
        sliding_window=cfg.sliding_window,
        normalize=cfg.normalize,
        embedding_batch_size=cfg.embedding_batch_size,
        cache_folder=cfg.cache_folder,
        trust_remote_code=cfg.trust_remote_code,
        device=cfg.device,
      )
    if provider == "sentence-transformers":
      embed = SBertEmbedding(
        model_name_or_path=cfg.model_name,
        # Sin max_length explicito, SBertEmbedding intenta leerlo de
        # self._model.config, que todavia no existe en ese punto de su
        # __init__, y siempre revienta con ValueError.
        max_length=cfg.max_length,
        cache_folder=cfg.cache_folder,
        device=cfg.device,
        embed_batch_size=cfg.embedding_batch_size,
        prompts={},
        default_prompt_name="",
        trust_remote_code=bool(getattr(cfg, "trust_remote_code", False)),
      )
      if str(getattr(cfg, "torch_dtype", "") or "").lower() in ("float16", "fp16", "half"):
        embed._model.half()
        # El modelo se carga en fp32 y .half() lo convierte, pero los bloques
        # fp32 se quedan retenidos en el caché del asignador de PyTorch: ~1.9 GB
        # de VRAM inutil en una GPU de 4 GB. empty_cache() los devuelve.
        import torch as _torch
        if _torch.cuda.is_available():
          _torch.cuda.empty_cache()
      return embed
    raise ValueError(f"Embedding provider '{provider}' no soportado.")


# ---------------------------------------------------------------------------
# Monkey-patch: método clone seguro en VectorIndexRetriever
# ---------------------------------------------------------------------------
import copy as _copy


def _rir_clone(self, **updates):
  """
  Devuelve una copia **ligera** del retriever.
  - Usa copy.copy() para replicar la configuración.
  - NO comparte el caché interno (_result_cache).
  - Permite sobreescribir atributos vía **updates.
  """
  new = _copy.copy(self)

  # blanquea caches mutables que no deben compartirse
  for cache_attr in ("_result_cache",):
    if hasattr(new, cache_attr):
      setattr(new, cache_attr, {})

  # aplica los overrides solicitados (p. ej. _doc_ids)
  for k, v in updates.items():
    setattr(new, k, v)

  return new


# aplica el parche (solo si aún no existe)
if not hasattr(VectorIndexRetriever, "clone"):
  VectorIndexRetriever.clone = _rir_clone
