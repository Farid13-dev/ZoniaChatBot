import re

from transformers import AutoTokenizer
import tiktoken

from rag.config.schema import (
  NodeParserConfig,
  MilvusConfig,
  EmbeddingConfig,
  LlmConfig,
  IndexRetrieverConfig,
  ResponseConfig,
  QuestionGenConfig

)
from rag.callbacks import CallbackManager
from rag.embeddings.openai import OpenAIEmbedding
from rag.node_parser.text.sentence import SentenceSplitter
from rag.embeddings.huggingface import HuggingFaceEmbedding
from rag.embeddings.sbert import SBertEmbedding
from rag.core.prompt_helper import PromptHelper
from rag.core.service_context import ServiceContext
from rag.question_gen.contextual_generator import ContextualQuestionGenerator  # o como lo llames
from rag.question_gen.prompt_gen import DEFAULT_SUB_QUESTION_PROMPT_TMPL, DEFAULT_CONTEXTUAL_SUBQUESTION_PROMPT_TMPL


class ContextualQuestionGeneratorPipeline:
  def __init__(
    self,
    llm_config: LlmConfig,
    embed_config: EmbeddingConfig,
    splitter_config: NodeParserConfig,
    qgen_config: QuestionGenConfig,
    embed_model=None,
  ):
    callback_manager = CallbackManager()

    # tokenizer = AutoTokenizer.from_pretrained(splitter_config.model_name_tokenizer)
    tokenizer = tiktoken.get_encoding(splitter_config.model_name_tokenizer)
    node_parser = SentenceSplitter(
      separator=splitter_config.separator,
      chunk_size=splitter_config.chunk_size,
      chunk_overlap=splitter_config.chunk_overlap,
      tokenizer=tokenizer.encode,
      paragraph_separator=splitter_config.paragraph_separator,
      secondary_chunking_regex=splitter_config.secondary_chunking_regex,
      callback_manager=callback_manager,
    )

    # Reutiliza el modelo del pipeline principal si nos lo pasan: cargar una
    # segunda copia de bge-m3 duplica ~1.1 GB de VRAM y en GPUs de 4 GB hace
    # que CUDA pagine a memoria del sistema.
    embed_model = embed_model or self.get_embed_mode(embed_config)

    prompt_helper = PromptHelper(
      tokenizer=tokenizer.encode,
      context_window=8192,
      num_output=512
    )

    self.service_context = ServiceContext(
      llm=llm_config,
      prompt_helper=prompt_helper,
      embed_model=embed_model,
      node_parser=node_parser,
      callback_manager=callback_manager,
    )

    self.qgen_config = qgen_config

  def run(self, query: str, context: list):
    # ⏹️ Desactiva si el flag está en False o max_subquestions <= 0
    if not self.qgen_config.subquestion_status or self.qgen_config.max_subquestions <= 0:
      return []

    context_chunks = [node.get_content().strip() for node in context if node.get_content()]
    context_text = "\n\n".join(context_chunks)

    question_generator = ContextualQuestionGenerator.from_defaults(
      service_context=self.service_context,
      prompt_template_str=DEFAULT_CONTEXTUAL_SUBQUESTION_PROMPT_TMPL,
      max_subquestions=self.qgen_config.max_subquestions
    )

    subquestions = question_generator.generate(
      context_str=context_text,
      query_str=query
    )

    return [sq.sub_question for sq in subquestions]

  async def arun(self, query: str, context: list):
    if not self.qgen_config.subquestion_status or self.qgen_config.max_subquestions <= 0:
      return []

    context_chunks = [node.get_content().strip() for node in context if node.get_content()]
    context_text = "\n\n".join(context_chunks)

    question_generator = ContextualQuestionGenerator.from_defaults(
      service_context=self.service_context,
      prompt_template_str=DEFAULT_CONTEXTUAL_SUBQUESTION_PROMPT_TMPL,
      max_subquestions=self.qgen_config.max_subquestions
    )

    subquestions = question_generator.generate(
      context_str=context_text,
      query_str=query
    )

    return [sq.sub_question for sq in subquestions]

  def get_embed_mode(self, config: EmbeddingConfig):
    provider = getattr(config, "provider", "huggingface").lower()

    if provider == "openai":
      return OpenAIEmbedding(
        model_name=config.model_name,
        api_key=config.api_key,
        normalize=config.normalize,
        embedding_batch_size=config.embedding_batch_size,
      )
    elif provider == "huggingface":
      return HuggingFaceEmbedding(
        model_name=config.model_name,
        tokenizer_name=config.tokenizer_name,
        pooling=config.pooling,
        max_length=config.max_length,
        stride=config.stride,
        sliding_window=config.sliding_window,
        normalize=config.normalize,
        embedding_batch_size=config.embedding_batch_size,
        cache_folder=config.cache_folder,
        trust_remote_code=config.trust_remote_code,
        device=config.device,
      )
    elif provider == "sentence-transformers":
      embed = SBertEmbedding(
        model_name_or_path=config.model_name,
        # Sin max_length explicito SBertEmbedding revienta: lo busca en
        # self._model.config, que aun no existe en ese punto de su __init__.
        max_length=config.max_length,
        cache_folder=config.cache_folder,
        device=config.device,
        embed_batch_size=config.embedding_batch_size,
        prompts={},
        default_prompt_name="",
        trust_remote_code=bool(getattr(config, "trust_remote_code", False)),
      )
      if str(getattr(config, "torch_dtype", "") or "").lower() in ("float16", "fp16", "half"):
        embed._model.half()
        # El modelo se carga en fp32 y .half() lo convierte, pero los bloques
        # fp32 se quedan retenidos en el caché del asignador de PyTorch: ~1.9 GB
        # de VRAM inutil en una GPU de 4 GB. empty_cache() los devuelve.
        import torch as _torch
        if _torch.cuda.is_available():
          _torch.cuda.empty_cache()
      return embed
    else:
      raise ValueError(f"❌ Proveedor de embeddings '{provider}' no soportado.")
