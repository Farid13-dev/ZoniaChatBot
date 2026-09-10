from typing import (
  Dict,
  Any,
  List, Optional
)
from dataclasses import dataclass


#
# from typing import Dict, Any, List, Optional
# from pydantic.dataclasses import dataclass

@dataclass
class ProcessingConfig:
  document_id: 2


@dataclass
class MilvusConfig:
  vectorstore_name: str
  collection_name: str
  insert_batch_size: int
  embedding_dim: int
  host: str
  port: str
  address: str
  uri: str
  user: str
  embedding_field: str
  primary_field: str
  text_field: str
  consistency_level: str
  overwrite: bool
  index_params: Dict[str, Any]
  search_params: Dict[str, Any]


@dataclass
class NodeParserConfig:
  splitter_mode: str  # "sentence", "token", "sentence_window", "hierarchical"
  model_name_tokenizer: str

  # Comunes a todos
  chunk_size: int
  chunk_overlap: int
  include_metadata: bool
  include_prev_next_rel: bool

  # SentenceSplitter & TokenTextSplitter
  separator: str
  backup_separators: Optional[List[str]]

  # SentenceSplitter
  paragraph_separator: str
  secondary_chunking_regex: str

  # SentenceWindowNodeParser
  window_size: Optional[int]

  # HierarchicalNodeParser
  chunk_sizes: Optional[List[int]]


@dataclass
class LlmConfig:
  provider: str
  model_name: str
  tokenizer_name: str
  api_key: str
  context_window: int
  max_tokens: int
  temperature: float
  top_p: float
  top_k: int
  num_beams: int
  do_sample: Optional[bool]
  use_cache: bool
  device_map: Optional[str]
  torch_dtype: str
  device: str
  # URL de un endpoint compatible con OpenAI (p. ej. Groq:
  # https://api.groq.com/openai/v1). Opcional: None = API de OpenAI.
  api_base: Optional[str] = None


@dataclass
class EmbeddingConfig:
  provider: str
  model_name: str
  tokenizer_name: str
  api_key: str
  pooling: str
  max_length: int
  normalize: bool
  embedding_batch_size: int
  device: str
  cache_folder: str
  trust_remote_code: bool
  # HuggingFaceEmbedding los usa (defaults 212 / True). Sin ellos, elegir
  # cualquier modelo con provider "huggingface" desde la UI de admin
  # petaba con AttributeError.
  stride: int = 212
  sliding_window: bool = True
  # "float16" reduce a la mitad la VRAM del modelo de embeddings. En GPUs
  # pequenas (4 GB) evita que CUDA pagine a memoria del sistema: medido
  # 4.05s -> 0.91s por embedding con bge-m3 en una GTX 1650.
  torch_dtype: Optional[str] = None


@dataclass
class QuestionGenConfig:
  subquestion_status: bool
  max_subquestions: int = 10  # valor por defecto


@dataclass
class RetrieverConfig:
  retriever_mode: str
  hybrid_mode: str
  similarity_top_k: int
  use_async: bool
  show_progress: bool
  # for vector store
  vector_store_query_mode: str
  sparse_top_k: int
  alpha: Optional[float]
  # list
  list_query_mode: str
  choice_batch_size: int



@dataclass
class RerankConfig:
  provider: str
  model_name: str
  tokenizer_name: str
  device: str
  top_n: int
  max_length: int
  batch_size: int
  token: str
  trust_remote_code: bool


@dataclass
class ResponseConfig:
    verbose: bool
    response_mode: str
    use_async: bool
    streaming: bool

@dataclass
class IndexRetrieverConfig:
  show_progress: bool
  store_nodes_override: bool
  insert_batch_size: int
  use_async: bool
  similarity_top_k: int
  sparse_top_k: int
  alpha: float
  vector_store_query_mode: str
