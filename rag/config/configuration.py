from omegaconf import DictConfig
from typing import Union

from .schema import (
  ProcessingConfig,
  MilvusConfig,
  NodeParserConfig,
  LlmConfig,
  EmbeddingConfig,
  RetrieverConfig,
  ResponseConfig,
  RerankConfig,
  QuestionGenConfig

)


class ConfigurationManager:
  def __init__(
    self,
    config: DictConfig,
  ) -> None:
    self.config = config
    print(self.config)

  def get_processing_config(self) -> ProcessingConfig:
    """create instace for data ingestion config"""
    configs = self.config.processing
    return ProcessingConfig(
      **configs
    )

  def get_db_config(self) -> Union[MilvusConfig]:
    """create instace for data ingestion config"""
    db_config = self.config.db
    if db_config.vectorstore_name == "milvus":
      return MilvusConfig(
        **db_config
      )
    else:
      raise ValueError("Not supported vector store. Please use either milvus or faiss.")

  def get_splitter_config(self) -> NodeParserConfig:
    return NodeParserConfig(**self.config.splitter.selected)

  def get_embed_config(self) -> EmbeddingConfig:
    return EmbeddingConfig(**self.config.embedding.selected)

  def get_llm_config(self) -> LlmConfig:
    return LlmConfig(**self.config.llm.selected)

  def get_rerank_config(self) -> RerankConfig:
    return RerankConfig(**self.config.rerank.selected)

  def get_index_retriever_config(self) -> RetrieverConfig:
    configs = self.config.retriever
    return RetrieverConfig(
      **configs
    )

  def get_response_config(self) -> ResponseConfig:
    response_cfg = self.config.response_config
    return ResponseConfig(
      verbose=response_cfg.verbose,
      response_mode=response_cfg.response_mode,
      use_async=response_cfg.use_async,
      streaming=response_cfg.streaming,
    )

  def get_milvus_config(self) -> MilvusConfig:
    return MilvusConfig(**self.config.db)

  def resolve_llm_from_config(self):
    from rag.llm.openai_llm import OpenAILLM  # ← sigue adentro para evitar import circular

    config = self.config.llm
    return OpenAILLM(
      model_name=config.model_name,
      api_key=config.api_key
    )

  def get_question_gen_config(self) -> QuestionGenConfig:
    configs = self.config.question_gen
    return QuestionGenConfig(**configs)
